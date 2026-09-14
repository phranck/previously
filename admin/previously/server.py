"""The HTTP layer: which addresses exist and what answers them.

Built on http.server from the standard library, which is enough for a handful
of routes on a single-user device and costs no interpreter, no pip and no venv.

Reading is open. Everything that changes the machine arrives as a POST and
is refused without the token, which token.py decides.
"""

import http.server
import json
import mimetypes
import pathlib
import urllib.parse

from . import change, config, files, kiosk, machines, pi
from .token import HEADER

VERSION = "0.1.0"

#: Where the browser's files live, beside the package rather than inside it.
WEB_ROOT = pathlib.Path(__file__).resolve().parent.parent / "web"

#: What a POST may ask of the emulator. A map rather than a chain of
#: comparisons, so the set of things this service can be asked to do is one
#: list somebody can read.
KIOSK_OPERATIONS = {
    "/api/kiosk/start": kiosk.start,
    "/api/kiosk/stop": kiosk.stop,
    "/api/kiosk/restart": kiosk.restart,
}

#: What a POST may ask of the board itself. Separate from the emulator's, and
#: separate on purpose: these two are the only things this tool does as root.
BOARD_OPERATIONS = {
    "/api/pi/reboot": "reboot",
    "/api/pi/poweroff": "poweroff",
}


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
        if route == "/api/pi":
            return self._json(pi.readings())
        if route == "/api/files":
            return self._json(files.tree(self.settings.state_directory))
        if route == "/api/token":
            return self._json({"valid": self._carries_the_token()})
        return self._file(route)

    def do_POST(self):
        """Routes a POST.

        Everything that arrives this way changes something, so the token is
        checked before anything looks at what was sent.
        """
        if not self._carries_the_token():
            return self._json({"error": "token required"}, status=403)

        route = urllib.parse.urlparse(self.path).path

        if route == "/api/machine":
            return self._change_machine()

        board = BOARD_OPERATIONS.get(route)
        if board is not None:
            finished, reason = kiosk.board(board, self.settings.runtime_directory)
            return self._json(
                {"ok": finished, "reason": reason, **self._status()},
                status=200 if finished else 409,
            )

        operation = KIOSK_OPERATIONS.get(route)
        if operation is None:
            return self._json({"error": "not found"}, status=404)

        finished, reason = operation(self.settings.runtime_directory)
        return self._json(
            {"ok": finished, "reason": reason, **self._status()},
            status=200 if finished else 409,
        )

    def _change_machine(self):
        """Makes the emulated machine the one the request names.

        The whole cycle lives in change.py: the guest is shut down properly,
        the file is copied and written, the machine comes back, and anything
        that does not come back is put straight back the way it was.
        """
        try:
            body = json.loads(self.rfile.read(
                int(self.headers.get("Content-Length") or 0)) or b"{}")
        except (ValueError, OSError):
            return self._json({"error": "unreadable request"}, status=400)

        finished, reason = change.to_machine(body.get("machine"), self.settings)
        return self._json(
            {"ok": finished, "reason": reason, **self._status()},
            status=200 if finished else 409,
        )

    def log_error(self, format, *args):
        """Always written, whatever the request turned out to be.

        Deliberately not routed through log_message below. Something spoke to
        this port and it was not a request this service could read, which is
        the sort of thing the journal is for.
        """
        super().log_message(format, *args)

    def log_message(self, format, *args):
        """Quieter than the default, which writes a line per request to stderr
        and therefore into the journal. A kiosk logs what went wrong.

        path is set by parse_request, so a request that fails earlier reaches
        this without one. Read defensively because the standard library decides
        when to call this, and it calls it from places the request never got
        past.
        """
        if not getattr(self, "path", "").startswith("/api/"):
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
        """What the machine is set to and whether it is running.

        "running" is about the emulator, not about the unit, because that is
        what somebody means by the question. The unit stays active either way:
        what it holds is a login shell, and the emulator is its grandchild.
        """
        unit = self.settings.kiosk_unit
        running = kiosk.emulator_is_running()
        answer = {
            "running": running,
            "held": kiosk.is_held(self.settings.runtime_directory),
            "console_active": kiosk.is_running(unit),
            "uptime_seconds": kiosk.uptime_seconds(unit) if running else None,
        }
        try:
            answer["configuration"] = config.read(self.settings.previous_config)
            # Which of the eleven this is exactly, or None where it is none of
            # them. Asked against the whole catalogue rather than against the
            # name the file gives itself, because Previous has no idea of Nitro
            # and a Nitro machine therefore calls itself by another's name.
            answer["configuration"]["catalogue"] = config.matching(
                self.settings.previous_config,
                [(machine.identifier, machines.settings_for(machine))
                 for machine in machines.CATALOGUE])
        except config.NotReadable as error:
            answer["configuration"] = None
            answer["error"] = str(error)
        # Whether the file has moved on since the emulator read it, which is
        # the one thing the configuration itself cannot say.
        answer["file"] = config.file_state(
            self.settings.previous_config, kiosk.emulator_uptime_seconds(),
            state_directory=self.settings.state_directory)
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

    @param settings - Settings, which says where to bind and what to read.
    @param token - Token, or None. Without one, every change is refused.
    """
    Handler.settings = settings
    Handler.token = token
    address = (settings.address, settings.port)
    with http.server.ThreadingHTTPServer(address, Handler) as httpd:
        print("previously %s on http://%s:%d"
              % (VERSION, settings.address, settings.port), flush=True)
        httpd.serve_forever()
