"""The HTTP layer: which addresses exist and what answers them.

Built on http.server from the standard library, which is enough for a handful
of routes on a single-user device and costs no interpreter, no pip and no venv.

Reading is open, with one exception at /api/screen. Everything that changes
the machine arrives as a POST and is refused without a signed in session,
which password.py decides.
"""

import email.utils
import hashlib
import http.cookies
import http.server
import json
import mimetypes
import pathlib
import threading
import urllib.parse

from . import (activity, change, config, files, grab, kiosk, machines, pi,
               release, saved, setup, systems, terminal, websocket)
from .password import COOKIE, SESSION_SECONDS, SMALLEST, Attempts, Sessions, acceptable

#: The release this tool belongs to. The one place it is written down, and
#: what packaging/build.py reads to number a package.
RELEASE = "1.0.1"


def _packaged_as():
    """@returns str - The version this copy was packaged as, or "".

    `packaging/build.py` writes the whole version into `version.txt` beside
    this file, because a package built between two releases is that release
    plus the commit it came from, and a machine has to be able to say which
    build it is running. A checkout has no such file and is the bare release,
    which is what it is.
    """
    try:
        return (pathlib.Path(__file__).resolve().parent / "version.txt") \
            .read_text(encoding="utf-8").strip()
    except OSError:
        return ""


#: What this copy calls itself, which is what every answer reports.
VERSION = _packaged_as() or RELEASE

#: The most a POST may carry. Everything sent here is a short object naming
#: one thing, so anything past this is not this interface talking.
LARGEST_BODY = 64 * 1024

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

#: Copying a disk and putting a copy back, by the job the privileged helper
#: knows them as. Two gigabytes each way, so neither is done here: the request
#: is left and the helper does the work.
COPY_OPERATIONS = {
    "/api/disk/backup": "back-up",
    "/api/disk/restore": "restore",
}


class Handler(http.server.BaseHTTPRequestHandler):
    """Answers one request.

    The settings arrive on the class rather than through the constructor,
    because http.server builds the handler itself and gives it no way to pass
    anything in.
    """

    settings = None
    #: The machine's own secret, the browsers that have given it, and how often
    #: each address has got it wrong lately. On the class for the same reason
    #: the settings are: http.server builds the handler itself.
    password = None
    sessions = None
    attempts = None

    #: Held whilst a shell session is open, so there is one at a time. A class
    #: attribute because there is one server, and http.server makes a handler
    #: per request.
    terminals = threading.Lock()
    server_version = "previously/" + VERSION
    #: Without this the base class announces the Python version to the network.
    sys_version = ""

    #: One connection carries as many files as the page needs, which is what
    #: HTTP/1.1 is for. Left at 1.0 the socket is closed after every answer,
    #: and on a Pi joined by Wi-Fi opening the next one costs two seconds:
    #: measured on 2026-09-29, thirty requests each paying it again, with a
    #: 1232-byte icon taking 8.7 seconds to arrive. Every answer here carries
    #: a Content-Length, which is what this needs to be safe.
    protocol_version = "HTTP/1.1"

    def do_GET(self):
        """Routes a GET. The API first, then files, then a refusal."""
        route = self.path.split("?", 1)[0]

        if route == "/api/health":
            return self._json(self._health())
        if route == "/api/status":
            return self._json(self._status())
        if route == "/api/pi":
            # The tool's own version rides along with the board's readings,
            # because the window that says what this Pi is running is where
            # somebody looks to find out what they are looking at. It comes
            # from here rather than from pi.py, which reads the board itself
            # and nothing else.
            return self._json({
                "version": VERSION,
                **pi.readings(self.settings.runtime_directory)})
        if route == "/api/activity":
            # Its own route rather than more of the one above, because this one
            # is asked once a second whilst a monitor is open and that one
            # forks three times to answer.
            return self._json(activity.readings())
        if route == "/api/files":
            return self._json(files.tree(
                self.settings.machines_file, self.settings.documents,
                self.settings.disks,
                config.booting_from(self.settings.previous_config),
                config.slots(self.settings.previous_config)))
        if route == "/api/machine/settled":
            return self._settled_configuration()
        if route == "/api/setup":
            return self._json(self._setup())
        if route == "/api/update":
            return self._json(self._update())
        if route == "/api/session":
            # How short a password may be travels with the answer, so the panel
            # that asks for one says the rule that will actually be applied
            # rather than a copy of it.
            return self._json({
                "claimed": bool(self.password and self.password.claimed),
                "signed_in": self._signed_in(),
                "smallest": SMALLEST,
            })
        if route == "/api/terminal":
            return self._terminal()
        if route == "/api/screen":
            return self._screen()
        if route == "/api/picture":
            return self._picture()
        return self._file(route)

    def do_POST(self):
        """Routes a POST.

        Everything that arrives this way changes something, so the session is
        checked before anything looks at what was sent. The three routes about
        the secret itself stand in front of that check, because they are how a
        browser comes to have a session at all.
        """
        route = urllib.parse.urlparse(self.path).path

        if not self._from_this_page():
            return self._json({"error": "another origin"}, status=403)

        if route == "/api/session":
            return self._sign_in()
        if route == "/api/session/end":
            return self._sign_out()
        if route == "/api/password":
            return self._choose_the_password()

        if not self._signed_in():
            return self._json({"error": "password required"}, status=403)

        if route == "/api/machine":
            return self._change_machine()
        if route == "/api/disk":
            return self._boot_a_disk()
        if route in COPY_OPERATIONS:
            return self._copy_a_disk(COPY_OPERATIONS[route])
        if route == "/api/disc":
            return self._put_a_disc_in()
        if route == "/api/disc/eject":
            return self._take_a_disc_out()
        if route == "/api/machine/save":
            return self._save_configuration()
        if route == "/api/machine/rename":
            return self._rename_configuration()
        if route == "/api/machine/remove":
            return self._remove_configuration()
        if route == "/api/picture/delete":
            return self._delete_picture()
        if route == "/api/setup":
            return self._ask_to_set_up()
        if route == "/api/update":
            return self._ask_to_update()

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
        body = self._sent()
        if body is None:
            return self._json({"error": "unreadable request"}, status=400)

        finished, told = change.to_machine(body.get("machine"), self.settings)
        return self._json(
            {"ok": finished, **told, **self._status()},
            status=200 if finished else 409,
        )

    def _boot_a_disk(self):
        """Makes the machine boot the disk of the system the request names.

        The same cycle as changing the machine, in the same module, because it
        is the same risk: Previous reads its configuration once at the start,
        so the guest goes down first and anything that does not come back is
        put straight back the way it was.

        What is different is how little is written. Three keys in `[HardDisk]`,
        pointing at one of the disks this tool put there, and nothing else in
        that section is touched.
        """
        body = self._sent()
        if body is None:
            return self._json({"error": "unreadable request"}, status=400)

        finished, told = change.to_disk(body.get("disk"), self.settings)
        return self._json(
            {"ok": finished, **told, **self._status()},
            status=200 if finished else 409,
        )

    def _save_configuration(self):
        """Keeps what the editor put together, under the name it was given.

        Nothing about the running machine changes. Saving a configuration and
        running one are two different acts, and the second is the route above,
        which shuts the guest down first.

        `replacing` is what the editor was opened on, where that was a saved
        configuration: then this one takes its place, under the same name or a
        new one. Opened on one of the eleven it carries nothing, because those
        cannot be changed and what comes out of editing one is a configuration
        of somebody's own.
        """
        body = self._sent()
        if body is None:
            return self._json({"error": "unreadable request"}, status=400)

        finished, told = saved.save(
            self.settings.machines_file,
            body.get("name"),
            body.get("configuration") or {},
            replacing=body.get("replacing"))
        return self._json({"ok": finished, **told}, status=200 if finished else 409)

    def _rename_configuration(self):
        """Gives a saved configuration another name, leaving its settings alone.

        Only a saved one. The eleven are the set to go back to, so a request
        naming one of those is answered with there being no such configuration
        to rename, which is true of the list this reads.
        """
        body = self._sent()
        if body is None:
            return self._json({"error": "unreadable request"}, status=400)

        finished, told = saved.rename(
            self.settings.machines_file, body.get("machine"), body.get("name"))
        return self._json({"ok": finished, **told}, status=200 if finished else 409)

    def _remove_configuration(self):
        """Takes a saved configuration out of the list.

        The file the emulator reads is untouched, so a machine running that
        configuration goes on running it. What goes is the entry in the viewer.
        """
        body = self._sent()
        if body is None:
            return self._json({"error": "unreadable request"}, status=400)

        finished, told = saved.remove(
            self.settings.machines_file, body.get("machine"))
        return self._json({"ok": finished, **told}, status=200 if finished else 409)

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
            # Which configuration this is exactly, or None where it is none of
            # them. Asked against the whole set rather than against the name the
            # file gives itself, because Previous has no idea of Nitro and a
            # Nitro machine therefore calls itself by another's name.
            answer["configuration"]["catalogue"] = config.matching(
                self.settings.previous_config, self._choices())
        except config.NotReadable as error:
            answer["configuration"] = None
            answer["error"] = str(error)
        # Whether the file has moved on since the emulator read it, which is
        # the one thing the configuration itself cannot say.
        answer["file"] = config.file_state(
            self.settings.previous_config, kiosk.emulator_uptime_seconds(),
            state_directory=self.settings.state_directory)
        answer["ready"] = self._ready(answer["configuration"] is not None)
        return answer

    def _ready(self, configured):
        """Whether this machine has been set up at all, and what is missing.

        @param configured - Whether previous.cfg could be read, which the
          caller has just found out and which is one of the three.
        @returns dict with the three facts and the one that follows from them.

        Answered here rather than worked out in the browser, because it is the
        same question the installer's own steps ask before they decide what to
        skip. A machine with nothing on it is not broken, it is new, and those
        two look identical from a page that has to guess.
        """
        emulator = setup.installed(setup.EMULATOR_PACKAGE)
        system = bool(systems.here(self.settings.disks))
        return {
            "emulator": emulator,
            "system": system,
            "configuration": configured,
            "set_up": emulator and system and configured,
        }

    def _choices(self):
        """Every configuration that can be named, the eleven first.

        @returns list of (identifier, settings) pairs, as config.matching takes
          them.

        The eleven come first, so a saved configuration holding the same values
        as one of them is reported as that one. They are the set whose names
        everybody knows, and a name is what the interface marks the machine in
        force by.

        A file of saved configurations that cannot be read leaves only the eleven
        here. This is a reading, and a reading has nothing to do about it: the
        moment somebody tries to change something, `saved.py` refuses and says
        why.
        """
        kept = ()
        try:
            kept = saved.read(self.settings.machines_file)
        except saved.NotReadable:
            pass
        return [(machine.identifier, machines.settings_for(machine))
                for machine in tuple(machines.CATALOGUE) + tuple(kept)]

    def _settled_configuration(self):
        """What a configuration would be, and what else could be chosen with it.

        The Config Editor asks this on every change. It holds six controls and no
        rules at all, so what a choice turns into and what may be chosen beside
        it are both answered here, and an interface can never offer a machine the
        emulator would correct underneath it.

        A reading rather than a change, so no password and nothing written: it says
        what Previous would make of a configuration and touches nothing.

        What comes back carries that configuration in exactly the shape
        /api/machine/save takes, so the editor posts back what it was handed
        rather than assembling one of its own. Beside it are the same facts about
        a machine that /api/status and /api/files carry, described by the same
        function, so the window says the processor, the memory and the chips in
        the words the rest of the interface already uses.
        """
        asked = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)

        def chosen(name):
            """@returns What the query said, or None where it said nothing."""
            return asked.get(name, [None])[0]

        machine = machines.drafted(
            kind=chosen("kind"),
            # As "1" and "0", because a query string carries text and a flag that
            # is absent has to read as off rather than as a word.
            turbo=chosen("turbo") == "1",
            colour=chosen("colour") == "1",
            dimensions=chosen("dimensions"),
            mhz=chosen("mhz"),
            memory=chosen("memory"),
            banks=chosen("banks"),
            dsp=chosen("dsp"),
            dsp_memory=chosen("dsp_memory"),
            floppy=chosen("floppy") == "1",
            optical=chosen("optical") == "1",
            ethernet=chosen("ethernet") == "1",
            socket=chosen("socket"),
            printer=chosen("printer") == "1",
        )
        settings = machines.settings_for(machine)
        return self._json({
            "configuration": saved.as_values(machine),
            "machine": config.describe(
                settings["System"], settings["Memory"], settings["Dimension"]),
            "offers": machines.offers(machine),
        })

    def _put_a_disc_in(self):
        """Puts a disc on a free slot beside the disk the machine is booting.

        The same cycle as changing a disk, and for a reason: Previous reads its
        configuration when it starts and never again, so a disc written into
        that file from here arrives when the machine next comes up.
        """
        body = self._sent()
        if body is None:
            return self._json({"error": "unreadable request"}, status=400)

        finished, told = change.to_disc(body.get("disc"), self.settings)
        return self._json({"ok": finished, **told, **self._status()},
                          status=200 if finished else 409)

    def _take_a_disc_out(self):
        """Takes the disc off the slot the request names, and never the disk."""
        body = self._sent()
        if body is None:
            return self._json({"error": "unreadable request"}, status=400)

        finished, told = change.eject_disc(body.get("slot"), self.settings)
        return self._json({"ok": finished, **told, **self._status()},
                          status=200 if finished else 409)

    def _copy_a_disk(self, job):
        """Asks the privileged helper to copy a disk, or to put a copy back.

        @param job - Which of the two, as `setup.JOBS` names them.

        Neither is done here. A disk is two gigabytes, the folder it lives in
        is one this service may not write, and the helper is already what puts
        things on the card and takes them off. So this leaves a request and the
        window watches it exactly as it watches an installation.
        """
        body = self._sent()
        if body is None:
            return self._json({"error": "unreadable request"}, status=400)

        taken, told = kiosk.ask_to_set_up(
            self.settings.runtime_directory, self.settings.setup_directory,
            job, body.get("system"), None, body.get("backup"))
        return self._json({"ok": taken, **told, **self._setup()},
                          status=200 if taken else 409)

    def _setup(self):
        """What can be put on this machine, what is on it, and what is happening.

        A reading, so it is open the way `/api/status` is. Nothing here is about
        whoever is sitting at the machine: it is what the card holds and how
        much room is left on it.

        The figures are read now rather than remembered. What is free changes
        with everything else on the machine, and a number from five minutes ago
        is what lets an unpack stop half way through a disk image.
        """
        disks = self.settings.disks
        here = systems.here(disks)
        # Which of them the machine is set to boot, so the window knows which
        # one cannot be started again. Compared whole, because two disks can be
        # called the same thing in two folders.
        booting = config.booting_from(self.settings.previous_config)
        return {
            "systems": [
                {
                    "identifier": system.identifier,
                    "name": system.name,
                    "size": system.size,
                    "unpacked": systems.UNPACKED_BYTES,
                    "here": system.identifier in here,
                    "booting": (booting is not None
                                and str(here.get(system.identifier)) == str(booting)),
                }
                for system in systems.CATALOGUE
            ],
            "default": systems.DEFAULT,
            # Which version is on the machine and which the archive offers, so
            # the window can say what an update would bring rather than
            # offering one that brings nothing.
            "emulator": setup.emulator(),
            "needs": systems.ROOM_BYTES,
            "room": systems.room_beside(disks),
            "progress": kiosk.setting_up(self.settings.setup_directory),
        }

    def _ask_to_set_up(self):
        """Leaves the request the privileged helper acts on.

        This service does none of the work and holds none of the privilege. It
        writes three names into a file, and `previously-setup.path` starts the
        program that reads them. What comes back says whether the request was
        taken, and `GET /api/setup` is where it is watched.
        """
        body = self._sent()
        if body is None:
            return self._json({"error": "unreadable request"}, status=400)

        taken, told = kiosk.ask_to_set_up(
            self.settings.runtime_directory, self.settings.setup_directory,
            body.get("do"), body.get("system"), body.get("machine"))
        # What dpkg and apt last said is about to stop being true, and the
        # window asks again the moment this answer arrives.
        setup.forget()
        return self._json({"ok": taken, **told, **self._setup()},
                          status=200 if taken else 409)

    def _update(self):
        """What this tool is, what is published, and how a replacement is going.

        A reading, so it is open the way `/api/status` and `/api/setup` are: what
        version a machine on this network runs is not anybody's private
        business, and the answer is the same one the About panel already shows.

        Nothing here touches the network. What GitHub said is kept for a quarter
        of an hour and looked up again in a thread, so this answers as quickly on
        a board with no internet as on one with it, and `published` is None until
        the first lookup comes back.

        What is installed is asked of dpkg rather than taken from `VERSION`
        above, because dpkg is what apt compares an update against and therefore
        what decides whether there is one. The two differ for as long as a
        package is in place and the service has not been restarted onto it, and
        that difference is worth seeing rather than hiding: the Raspberry Pi
        window shows what is answering beside what is installed.
        """
        newest = release.published()
        here = setup.version_of(release.PACKAGE)
        running = kiosk.setting_up(self.settings.setup_directory)
        return {
            "installed": here,
            "published": newest["version"] if newest else None,
            "newer": (setup.newer_than(here, newest["version"]) if newest
                      else False),
            # Only a run that is about this tool. The helper takes one job at a
            # time and writes them all into the same record, so without this the
            # window would draw a two gigabyte unpack as though it were the
            # update somebody pressed.
            "progress": (running if running
                         and running.get("do") == setup.UPDATE_TOOL else None),
        }

    def _ask_to_update(self):
        """Leaves the request that replaces this tool with the newest release.

        This service fetches nothing and holds no privilege. It writes the name
        of one job into a file, and `previously-setup.path` starts the program
        that reads it, which is the same road an installation takes.

        The answer goes out before anything is replaced, because it has to: the
        run this asks for stops this service and starts the new one, so a reply
        written afterwards would be written by a process that is no longer there.
        `GET /api/update` is where the rest of it is watched.
        """
        taken, told = kiosk.ask_to_set_up(
            self.settings.runtime_directory, self.settings.setup_directory,
            setup.UPDATE_TOOL)
        return self._json({"ok": taken, **told, **self._update()},
                          status=200 if taken else 409)

    def _terminal(self):
        """Carries a login on a WebSocket, to one browser at a time.

        No password of ours here, and that is the point of it: what is on the
        other end is this machine's own SSH server, so whoever is connecting
        says who they are and proves it to sshd the way they would at any other
        door into this machine. Our own password guards what this service does
        itself.
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
            # Written out rather than sent through send_response, because what
            # follows is not HTTP at all: this socket becomes a WebSocket the
            # moment these lines are on it, so nothing more may be added to
            # the answer and nothing may be kept open for a next request.
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

        The one reading behind the password. Everything else this service tells
        is about the machine as a thing, so which processor it has and whether
        it is running, and a picture is about whoever is sitting at it: their
        files, their windows and whatever they have open. That is a different
        question and it takes the password.
        """
        if not self._signed_in():
            return self._json({"error": "password required"}, status=403)

        picture = grab.take()
        if picture is None:
            return self._json({"error": "no screen"}, status=503)

        # Kept as well as sent, because a screenshot is a document: it goes
        # into the folder the File Viewer shows as Documents/Pictures, where
        # the emulated machine can reach it too. Whether that worked does not
        # decide what the browser gets, which is the picture either way.
        kept = grab.keep(picture, files.picture_directory(self.settings.documents))

        self.send_response(200)
        self.send_header("Content-Type", grab.PNG)
        self.send_header("Content-Length", str(len(picture)))
        # The name it was filed under, so the page can say where it went
        # without asking for the whole tree again.
        if kept is not None:
            self.send_header("X-Previously-Kept", kept.name)
        # Every one of these is a different moment, and a browser that kept
        # the first would show that moment for ever.
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(picture)

    def _delete_picture(self):
        """Takes one picture out of the folder pictures are kept in.

        A POST, because it changes something, which is what makes the session
        checked before this is reached at all. What is named is read as a name
        rather than as a way to a file, so there is nothing here that reaches
        outside that one folder and nothing that deletes anything but a
        picture.
        """
        asked = (self._sent() or {}).get("name")
        gone = files.remove_picture(self.settings.documents, asked)
        return self._json({"ok": gone}, status=200 if gone else 404)

    def _sent(self):
        """What a POST carried.

        @returns dict, empty where nothing was sent, and None where something
          was sent that cannot be read as an object.

        The two are kept apart because they are different mistakes: a request
        that names nothing is answered by whatever it asked of, and a request
        whose body is not JSON is the caller's error and is told so.
        """
        length = int(self.headers.get("Content-Length") or 0)
        if length == 0:
            return {}
        if length > LARGEST_BODY:
            return None
        try:
            found = json.loads(self.rfile.read(length))
        except (ValueError, OSError):
            return None
        return found if isinstance(found, dict) else None

    def _picture(self):
        """Answers with one picture out of the folder pictures are kept in.

        Behind the password for the same reason the route that takes one is: a
        picture of the screen shows whoever was sitting at it.

        Asked for by name and by nothing else. The name is read as a name, so
        a request naming a path is answered with the file of that name if
        there is one and with nothing if there is not, and there is no way
        from here to a file outside that folder.
        """
        if not self._signed_in():
            return self._json({"error": "password required"}, status=403)

        asked = urllib.parse.parse_qs(
            urllib.parse.urlparse(self.path).query).get("name", [""])[0]
        where = files.picture_directory(self.settings.documents)
        if where is None or not asked:
            return self._json({"error": "not found"}, status=404)

        # The name of the file and not a way to it: everything up to the last
        # separator is thrown away, so "../../etc/passwd" asks for "passwd" in
        # the pictures folder, which is not there.
        wanted = where / pathlib.PurePosixPath(asked).name
        if not (wanted.is_file() and files.is_a_picture(wanted)):
            return self._json({"error": "not found"}, status=404)

        body = wanted.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type",
                         mimetypes.guess_type(wanted.name)[0] or grab.PNG)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _sign_in(self):
        """Takes the password and hands back a session.

        Answered the same way whether the password was wrong or the machine has
        none yet, because the difference is worth nothing to whoever asked and
        tells anybody else which machines are still unclaimed.

        A source that keeps getting it wrong is refused for a while, which is
        the one attack a hash on its own does not answer: a machine on this
        network could otherwise work through a list at network speed.
        """
        source = self.client_address[0]
        if self.attempts.too_many(source):
            return self._json({"error": "too many attempts"}, status=429)

        typed = (self._sent() or {}).get("password")
        if self.password is None or not self.password.matches(typed):
            self.attempts.wrong(source)
            return self._json({"error": "refused"}, status=403)

        self.attempts.forget(source)
        return self._json({"ok": True}, cookie=self.sessions.open())

    def _sign_out(self):
        """Ends this browser's session and takes its cookie away."""
        self.sessions.forget(self._session_offered())
        return self._json({"ok": True}, cookie="")

    def _choose_the_password(self):
        """Sets this machine's password, and signs the browser in with it.

        Open whilst the machine is unclaimed, which is how the first browser to
        reach a fresh installation claims it without fetching anything from the
        Pi. Once there is a password, changing it needs the one there is, which
        a signed in session already proves.

        Every other session ends here, so a password given to somebody who
        should not have it can be taken back by choosing a new one.
        """
        if self.password is None:
            return self._json({"error": "nowhere to keep it"}, status=503)
        if self.password.claimed and not self._signed_in():
            return self._json({"error": "password required"}, status=403)

        typed = (self._sent() or {}).get("password")
        if not acceptable(typed):
            return self._json({"error": "not a password"}, status=400)

        try:
            self.password.set(typed)
        except OSError:
            return self._json({"error": "cannot be kept"}, status=503)

        self.sessions.forget_them_all()
        return self._json({"ok": True}, cookie=self.sessions.open())

    def _signed_in(self):
        """Whether this request carried a session that is still open.

        False where the service has none to give, because a service that cannot
        hold a session should refuse every change rather than accept them all.
        """
        if self.sessions is None:
            return False
        return self.sessions.holds(self._session_offered())

    def _session_offered(self):
        """@returns str - The session in this request's cookies, or None."""
        jar = http.cookies.SimpleCookie(self.headers.get("Cookie", ""))
        found = jar.get(COOKIE)
        return found.value if found else None

    def _from_this_page(self):
        """Whether a POST came from this service's own page.

        A cookie rides along with every request a browser makes to this host,
        including one a page somewhere else caused, so the session on its own
        would let another site act here. A browser states the origin it is
        posting from whenever that origin is not this one, and a request that
        states a different one is refused.

        A request carrying no origin at all is something other than a browser
        form, such as curl, and is left to the session check below.
        """
        origin = self.headers.get("Origin")
        if not origin:
            return True
        return urllib.parse.urlparse(origin).netloc == self.headers.get("Host")

    # -- how anything is sent --------------------------------------------

    def _json(self, payload, status=200, cookie=None):
        """Answers with an object, and with a session where one was opened.

        @param payload - What to send.
        @param status - The status line.
        @param cookie - A session to hand the browser, "" to take the one it
          has away, or None to leave its cookies alone.

        HttpOnly, so no script on the page can read the session, which is the
        one thing a secret in localStorage could never say for itself.
        SameSite=Strict, so the browser does not send it with a request another
        site caused at all. Not Secure: this service speaks plain HTTP by
        decision, and a cookie marked Secure would never be sent.
        """
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        # Nothing here is worth caching: every answer is about right now.
        self.send_header("Cache-Control", "no-store")
        if cookie is not None:
            self.send_header("Set-Cookie", "%s=%s; Path=/; Max-Age=%d; HttpOnly; SameSite=Strict"
                             % (COOKIE, cookie, SESSION_SECONDS if cookie else 0))
        self.end_headers()
        self.wfile.write(body)

    def _file(self, route):
        """Serves a file from the web directory, and nothing outside it.

        Everything here says how long it is worth keeping and what it is, so a
        reload asks about a file rather than fetching it again. A browser that
        already has it sends what it holds, and this answers 304 with nothing
        in it.

        The pictures, the faces and the one library are given a day, because
        they change when a new package is installed and at no other time. The
        page, the script and the stylesheet are given none: they change on
        every build, and being told 304 costs a few bytes on a connection that
        is already open.
        """
        target = safe_path(WEB_ROOT, route)
        if target is None or not target.is_file():
            return self._json({"error": "not found"}, status=404)

        body = target.read_bytes()
        tag = '"%s"' % hashlib.sha1(body).hexdigest()
        written = email.utils.formatdate(target.stat().st_mtime, usegmt=True)
        keeping = ("public, max-age=%d" % KEEP_SECONDS
                   if route.startswith(KEPT) else "no-cache")

        if self._already_has(tag, target.stat().st_mtime):
            self.send_response(304)
            self.send_header("ETag", tag)
            self.send_header("Cache-Control", keeping)
            self.send_header("Content-Length", "0")
            return self.end_headers()

        kind = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("ETag", tag)
        self.send_header("Last-Modified", written)
        self.send_header("Cache-Control", keeping)
        self.end_headers()
        self.wfile.write(body)

    def _already_has(self, tag, changed_at):
        """Whether the browser is holding this exact file.

        @param tag - The ETag of what is here now.
        @param changed_at - When the file last changed, as a timestamp.
        @returns bool

        The tag is asked about first, because it is about the bytes and the
        date is only about the file. A date is compared by the second, and a
        file written in the same second as the answer went out would otherwise
        read as unchanged for ever.
        """
        held = self.headers.get("If-None-Match")
        if held:
            return any(one.strip() in (tag, "*") for one in held.split(","))

        since = self.headers.get("If-Modified-Since")
        if not since:
            return False
        try:
            asked = email.utils.parsedate_to_datetime(since).timestamp()
        except (TypeError, ValueError):
            return False
        return int(changed_at) <= int(asked)


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


def serve(settings, password=None):
    """Runs the service until it is stopped.

    @param settings - Settings, which says where to bind and what to read.
    @param password - Password, or None. Without one, every change is refused.

    The sessions and the attempt count are made here rather than handed in,
    because both are this run's own: a restart signs everybody out and forgets
    who was guessing.
    """
    Handler.settings = settings
    Handler.password = password
    Handler.sessions = Sessions()
    Handler.attempts = Attempts()
    address = (settings.address, settings.port)
    with http.server.ThreadingHTTPServer(address, Handler) as httpd:
        print("previously %s on http://%s:%d"
              % (VERSION, settings.address, settings.port), flush=True)
        httpd.serve_forever()


#: What is kept rather than asked about again: the pictures, the faces the
#: Terminal is set in, and the one library this interface takes. They change
#: when a package is installed and at no other time, so a browser holding
#: yesterday's copy is holding the right one. Everything else under web/ is
#: written by every build and is asked about each time.
KEPT = ("/parts/", "/fonts/", "/vendor/")

#: For how long. A day rather than a year, because a picture that does change
#: should not outlive the package that brought it by much, and because the
#: cost of asking again is one round trip on a connection that is already
#: open.
KEEP_SECONDS = 24 * 60 * 60
