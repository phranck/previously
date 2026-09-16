"""The HTTP layer: which addresses exist and what answers them.

Built on http.server from the standard library, which is enough for a handful
of routes on a single-user device and costs no interpreter, no pip and no venv.

Reading is open, with one exception at /api/screen. Everything that changes
the machine arrives as a POST and is refused without the token, which token.py
decides.
"""

import http.server
import json
import mimetypes
import pathlib
import threading
import urllib.parse

from . import change, config, files, grab, kiosk, machines, pi, terminal, websocket
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

    #: Held whilst a shell session is open, so there is one at a time. A class
    #: attribute because there is one server, and http.server makes a handler
    #: per request.
    terminals = threading.Lock()
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
        if route == "/api/terminal":
            return self._terminal()
        if route == "/api/screen":
            return self._screen()
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
            finished, told = kiosk.board(board, self.settings.runtime_directory)
            return self._json(
                {"ok": finished, **told, **self._status()},
                status=200 if finished else 409,
            )

        operation = KIOSK_OPERATIONS.get(route)
        if operation is None:
            return self._json({"error": "not found"}, status=404)

        finished, told = operation(self.settings.runtime_directory)
        return self._json(
            {"ok": finished, **told, **self._status()},
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

        finished, told = change.to_machine(body.get("machine"), self.settings)
        return self._json(
            {"ok": finished, **told, **self._status()},
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

    def _terminal(self):
        """Carries a login on a WebSocket, to one browser at a time.

        No token here, and that is the point of it: what is on the other end
        is this machine's own SSH server, so whoever is connecting says who
        they are and proves it to sshd the way they would at any other door
        into this machine. The token guards what this service does itself.
        """
        if not websocket.wants_a_socket(self.headers):
            return self._json({"error": "not a websocket request"}, status=400)

        speaks = websocket.offered(self.headers.get("Sec-WebSocket-Protocol"))
        if not speaks or speaks[0] != websocket.PROTOCOL:
            return self._json({"error": "another protocol"}, status=400)

        key = self.headers.get("Sec-WebSocket-Key")
        if not key:
            return self._json({"error": "no key"}, status=400)

        # One at a time. A second browser would get a second session that the
        # first one cannot see, which is one more thing running than anybody
        # is watching.
        if not self.terminals.acquire(blocking=False):
            return self._json({"error": "a session is already open"}, status=409)

        self.close_connection = True
        try:
            # Written out rather than sent through send_response, because that
            # answers in the protocol version this handler speaks and this
            # handler speaks HTTP/1.0. A browser refuses a handshake that is
            # not answered in 1.1, and raising the version for every other
            # answer as well would change how they are all framed.
            self.log_request(101)
            self.wfile.write(
                b"HTTP/1.1 101 Switching Protocols\r\n"
                b"Upgrade: websocket\r\n"
                b"Connection: Upgrade\r\n"
                + b"Sec-WebSocket-Accept: " + websocket.accepts(key).encode() + b"\r\n"
                + b"Sec-WebSocket-Protocol: " + websocket.PROTOCOL.encode() + b"\r\n"
                b"\r\n")
            self.wfile.flush()

            connection = websocket.Connection(self.rfile, self.connection)
            # A browser that connects and says nothing would otherwise hold
            # the one session there is for as long as it liked.
            self.connection.settimeout(terminal.FIRST_WORD_SECONDS)
            session = terminal.open_for(connection)
            if session is None:
                return connection.close()
            self.connection.settimeout(None)
            terminal.attach(session, connection)
        finally:
            self.terminals.release()

    def _screen(self):
        """Answers with a picture of what the emulated machine is showing.

        The one reading behind the token. Everything else this service tells
        is about the machine as a thing, so which processor it has and whether
        it is running, and a picture is about whoever is sitting at it: their
        files, their windows and whatever they have open. That is a different
        question and it takes the token.
        """
        if not self._carries_the_token():
            return self._json({"error": "token required"}, status=403)

        picture = grab.take()
        if picture is None:
            return self._json({"error": "no screen"}, status=503)
        self.send_response(200)
        self.send_header("Content-Type", grab.PNG)
        self.send_header("Content-Length", str(len(picture)))
        # Every one of these is a different moment, and a browser that kept
        # the first would show that moment for ever.
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(picture)

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
