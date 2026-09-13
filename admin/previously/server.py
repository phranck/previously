"""The HTTP layer: which addresses exist and what answers them.

Built on http.server from the standard library, which is enough for a handful
of routes on a single-user device and costs no interpreter, no pip and no venv.

Nothing here writes anything. Every route reads.
"""

import http.server
import json
import mimetypes
import pathlib

from . import config, kiosk, tls
from .token import HEADER

VERSION = "0.1.0"

#: Where the browser's files live, beside the package rather than inside it.
WEB_ROOT = pathlib.Path(__file__).resolve().parent.parent / "web"


class Handler(http.server.BaseHTTPRequestHandler):
    """Answers one request.

    The settings arrive on the class rather than through the constructor,
    because http.server builds the handler itself and gives it no way to pass
    anything in.
    """

    settings = None
    token = None
    server_version = "previously/" + VERSION
    #: Without this the base class announces the Python version to the network.
    sys_version = ""

    def do_GET(self):
        """Routes a GET. The API first, then files, then a refusal."""
        route = self.path.split("?", 1)[0]

        if route == "/api/health":
            return self._json(self._health())
        if route == "/api/status":
            return self._json(self._status())
        if route == "/api/token":
            return self._json({"valid": self._carries_the_token()})
        return self._file(route)

    def do_POST(self):
        """Routes a POST.

        Everything that arrives this way changes something, so the token is
        checked before anything looks at what was sent. There is nothing to
        route to yet: writing a configuration is #2 and controlling the kiosk
        is #4, and both land here.
        """
        if not self._carries_the_token():
            return self._json({"error": "token required"}, status=403)
        return self._json({"error": "not found"}, status=404)

    def log_message(self, format, *args):
        """Quieter than the default, which writes a line per request to stderr
        and therefore into the journal. A kiosk logs what went wrong."""
        if not self.path.startswith("/api/"):
            return
        super().log_message(format, *args)

    # -- what the routes answer ------------------------------------------

    def _health(self):
        """Enough to tell a working installation from a broken one.

        Whether the configuration can be read is the one thing worth checking
        here, because everything else the tool does depends on it.
        """
        path = self.settings.previous_config
        return {
            "version": VERSION,
            "config_path": str(path),
            "config_readable": path.is_file(),
        }

    def _status(self):
        """What the machine is set to and whether it is running."""
        unit = self.settings.kiosk_unit
        running = kiosk.is_running(unit)
        answer = {
            "running": running,
            "uptime_seconds": kiosk.uptime_seconds(unit) if running else None,
        }
        try:
            answer["configuration"] = config.read(self.settings.previous_config)
        except config.NotReadable as error:
            answer["configuration"] = None
            answer["error"] = str(error)
        return answer

    def _carries_the_token(self):
        """Whether this request carried the token.

        False where the service has none, because a service that cannot read
        its own secret should refuse every change rather than accept them all.
        """
        if self.token is None:
            return False
        return self.token.matches(self.headers.get(HEADER))

    # -- how anything is sent --------------------------------------------

    def _json(self, payload, status=200):
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        # Nothing here is worth caching: every answer is about right now.
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _file(self, route):
        """Serves a file from the web directory, and nothing outside it."""
        target = safe_path(WEB_ROOT, route)
        if target is None or not target.is_file():
            return self._json({"error": "not found"}, status=404)

        body = target.read_bytes()
        kind = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def safe_path(root, route):
    """Resolves a request path inside a directory, or refuses.

    @param root - pathlib.Path the request may not leave.
    @param route - The path from the request line.
    @returns pathlib.Path inside root, or None where it would escape.

    A request is a string from the network, so `../` in it is a question about
    which file, not a typing mistake. Resolving both sides and comparing is
    what makes the answer independent of how the escape was spelled.
    """
    relative = route.lstrip("/") or "index.html"
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError:
        return None
    return candidate


def serve(settings, token=None):
    """Runs the service until it is stopped.

    @param settings - Settings, which says where to bind, what to read and
      which certificate to present where one is configured.
    @param token - Token, or None. Without one, every change is refused.
    @raises tls.NotUsable where a certificate is configured and cannot be used.
      Nothing is bound in that case, so a broken certificate is a service that
      does not come up rather than one quietly serving in the clear.

    A client speaking plain HTTP to a TLS port needs no handling here. The
    handshake fails inside get_request, socketserver catches OSError there, and
    ssl.SSLError is one, so the attempt is dropped without a traceback.
    """
    context = tls.context(settings.certificate, settings.private_key)

    Handler.settings = settings
    Handler.token = token
    address = (settings.address, settings.port)
    with http.server.ThreadingHTTPServer(address, Handler) as httpd:
        if context is not None:
            httpd.socket = context.wrap_socket(httpd.socket, server_side=True)
        print("previously %s on %s://%s:%d"
              % (VERSION, settings.scheme, settings.address, settings.port),
              flush=True)
        httpd.serve_forever()
