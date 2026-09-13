"""The HTTP layer: which addresses exist and what answers them.

Built on http.server from the standard library, which is enough for a handful
of routes on a single-user device and costs no interpreter, no pip and no venv.

Nothing here writes anything. Every route reads.
"""

import http.server
import json
import mimetypes
import pathlib

from . import config, kiosk

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
        return self._file(route)

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


def serve(settings):
    """Runs the service until it is stopped.

    @param settings - Settings, which says where to bind and what to read.
    """
    Handler.settings = settings
    address = (settings.address, settings.port)
    with http.server.ThreadingHTTPServer(address, Handler) as httpd:
        print("previously %s on http://%s:%d"
              % (VERSION, settings.address, settings.port), flush=True)
        httpd.serve_forever()
