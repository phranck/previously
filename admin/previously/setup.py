"""What root does to this machine, and the only thing root does.

    python3 -m previously.setup

Started by `previously-setup.path` when the admin tool leaves a request in its
runtime directory, and by nothing else. It reads that request, does the work,
writes down what it is doing as it goes, and ends. The tool itself stays
unprivileged: it writes a small file and reads another one.

This module is the whole of the privileged surface added for installing. There
are no routes in it, nothing is parsed from the network, and nothing that
arrives from a browser is ever a path, a URL or a command. A request names a
job, a system and a machine, and all three are looked up in tables that live
here and in `systems.py` and `machines.py`. A name that is not in the table
refuses the whole request.

The work itself is one machine being set up: the tools, the archive, the
emulator, a system's disk, the configuration, the console, the quiet boot, the
sound, and the start that leaves a fresh machine running rather than waiting for
a reboot. Each step skips what it finds already done. Every step that changes
something records how to undo exactly that, and a failure walks the record
backwards.

These steps are written here and nowhere else. `install.sh` installs this tool
and asks for the `install` job, which is the job the Installer window asks for
too. The one thing that script still writes itself is the console, under
`--update-admin`, and `_autostart_block` says why.
"""

import datetime
import grp
import hashlib
import json
import os
import pathlib
import pwd
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error

from . import fetching, files, machines, release, systems
from .answers import told
from .settings import Settings

#: What the tool calls the request, inside its own runtime directory.
#: `previously-setup.path` watches for this name and starts this program.
REQUEST = "setup"

#: What the job that replaces this tool with the newest release is called. Named
#: here because two halves ask about it, the helper that carries it out and the
#: route the browser watches it from, and a string written into both is one that
#: can be written differently in one of them.
UPDATE_TOOL = "update-tool"

#: The most a request may be. Everything one can say is four names, so anything
#: past this is not the tool talking.
LARGEST_REQUEST = 4096

#: The most a copy's name may be. It is matched against the listing of the
#: folder copies are kept in rather than joined onto a path, and a name longer
#: than any file can have is one nothing will match.
LONGEST_NAME = 255

#: Where this writes what it is doing. Its own directory rather than the tool's,
#: and that is the point: the tool's runtime directory belongs to an
#: unprivileged user, so a file root wrote there could be replaced by a link to
#: somewhere else between one write and the next. This one is root's, made by
#: `RuntimeDirectory=` in the unit, and the tool only reads it.
OUR_DIRECTORY = pathlib.Path("/run/previously-setup")
PROGRESS = "progress.json"

#: Where it is written down who owns the emulator: the drop-in the package
#: writes beside the tool's unit on install. The user is read from there rather
#: than named again here, because a second copy would be a second answer.
OWNER_FILE = pathlib.Path("/etc/systemd/system/previously.service.d/owner.conf")

#: What the machine has to be for the emulator's package to fit. Raspberry Pi
#: OS before trixie carries no SDL3, and Previous is built against it.
ARCHITECTURE = "arm64"
RELEASE = "trixie"

#: The kiosk compositor, the unpacker for a system archive, and the two tools
#: the admin uses to reach the emulator: xdotool presses its keys and
#: ImageMagick reads its screen.
TOOLS = ("cage", "7zip", "xdotool", "imagemagick")

#: What carries the sound. PipeWire connects the emulator to itself rather than
#: to a card, so a speaker plugged in later is heard without restarting it.
SOUND = ("pipewire", "wireplumber", "pipewire-alsa")

#: The archive Previous comes from, pinned so that nothing else does.
REPOSITORY_HOST = "wmlive.rumbero.org"
REPOSITORY_URL = "https://%s/repo" % REPOSITORY_HOST
REPOSITORY_SUITE = "wmlive-trixie"
REPOSITORY_KEY = pathlib.Path("/etc/apt/keyrings/wmlive.asc")
REPOSITORY_SOURCE = pathlib.Path("/etc/apt/sources.list.d/wmlive.sources")
REPOSITORY_PINS = pathlib.Path("/etc/apt/preferences.d/wmlive")
EMULATOR_PACKAGE = "previous"

#: The machine a fresh configuration describes: the cube with the turbo board,
#: which is what the one-liner gets as well. Where the disks live, where that
#: configuration goes and where a picture is filed all come from
#: `/etc/previously/config.ini`, which is the same file the tool reads.
DEFAULT_MACHINE = "nextcube-turbo"

#: Where the console logs in without being asked, and what tells `login` to keep
#: quiet about the message of the day.
AUTOLOGIN = pathlib.Path("/etc/systemd/system/getty@tty1.service.d/autologin.conf")
HUSHLOGIN = ".hushlogin"

#: The two files that decide what the screen shows before NeXTSTEP does, and
#: what a copy of one of them is called whilst this holds it.
CMDLINE = pathlib.Path("/boot/firmware/cmdline.txt")
CONFIG_TXT = pathlib.Path("/boot/firmware/config.txt")
BACKUP = ".previously.backup"

#: What is added to the kernel's command line to silence the boot, and the line
#: that stops the firmware drawing its own picture first.
QUIET_ARGUMENTS = ("quiet", "loglevel=0", "logo.nologo",
                   "vt.global_cursor_default=0", "systemd.show_status=false")
NO_SPLASH = "disable_splash=1"

#: Where the console's autostart is written, and what fences it so that taking
#: it out again leaves whatever else the file holds.
PROFILE = ".profile"
AUTOSTART_OPENS = "# >>> nextstep-rpi >>>"
AUTOSTART_CLOSES = "# <<< nextstep-rpi <<<"

#: Where the emulator runs, and therefore where it writes a screen grab. Its
#: own directory rather than the home, so the tool needs write access to that
#: one place and to nothing else.
WORK_DIRECTORY = ".cache/previously"

#: The service's own runtime directory, which is a tmpfs the unit makes.
RUNTIME = "/run/previously"

#: The file the tool creates to hold the emulator down, which the autostart
#: below waits on.
HOLD = RUNTIME + "/hold"

#: Where the console writes down an emulator that ended badly, one line each.
#: In the runtime directory because it is a tmpfs: the file is gone at every
#: boot, so what is in it is what happened since this board came up, and the
#: window reading it has nothing to work out.
#:
#: Core dumps are a different answer to the same question and this project
#: takes neither: Debian's own `/etc/security/limits.d/10-coredump-debian.conf`
#: sets the soft limit to 0 for every user, so nothing is written. Nine of
#: them, 340 MB, sat in the home for two days and nobody ever read one. A line
#: saying a crash happened is what a person actually wants.
CRASHES = RUNTIME + "/crashes"

#: What a speaker is set to the first time it is seen. WirePlumber ships 0.064,
#: which is inaudible once NeXTSTEP's own sounds are played through it. This is
#: 85 per cent linear, cubed, because that is the scale the setting takes.
SOUND_CONFIGURATION = pathlib.Path(
    "/etc/wireplumber/wireplumber.conf.d/50-nextstep.conf")
VOLUME = "0.614"

#: How much of a download to take at a time, and how often to say how far it
#: has got. A report per chunk would rewrite the progress file two thousand
#: times for one archive.
CHUNK_BYTES = 256 * 1024
SAY_EVERY_SECONDS = 0.5

#: How long to wait for a download to answer at all. Generous, because the two
#: places this fetches from are both somebody else's and a Pi is often on Wi-Fi,
#: and bounded, because a fetch that hangs holds a progress bar that says
#: nothing.
FETCH_SECONDS = 60

#: How much of a disk to copy at a time. Larger than a download's chunk,
#: because this is a card reading and writing itself and there is no network in
#: the way.
COPY_BYTES = 4 * 1024 * 1024

#: What a step is doing at this moment. One step can fetch, then unpack, then
#: move, and each of those takes minutes of its own, so a person watching is
#: told which of them is running rather than watching one bar cover all three.
#: The browser says these in words; `tests/test_strings.py` holds it to that.
FETCHING = "fetching"
UNPACKING = "unpacking"
COPYING = "copying"
CHECKING = "checking"
INSTALLING = "installing"
DOINGS = (FETCHING, UNPACKING, COPYING, CHECKING, INSTALLING)

#: How long to wait for one command. An unpack of two gigabytes on a Pi is the
#: long one, and a step that hangs is worse than one that fails because nothing
#: says so.
COMMAND_SECONDS = 1800

#: And how long to wait for one that only reads, such as asking dpkg what is
#: installed. A question that hangs is worse than one that fails, because the
#: page waits with it.
TIMEOUT_SECONDS = 5

#: How long what dpkg and apt said is worth keeping. The Installer asks twice a
#: second whilst its window is open, and those answers change when something is
#: installed and at no other time.
REMEMBER_SECONDS = 5

#: The last of those answers and when it was given, or None.
_REMEMBERED = None


class Refused(Exception):
    """A step could not be taken, said in a way the browser can read out.

    @param reason - What happened, as `answers.told` takes it.
    @param values - Whatever the sentence needs.
    """

    def __init__(self, reason, **values):
        super().__init__(reason)
        self.told = told(reason, **values)


# -- what a request may say --------------------------------------------------


#: Every job, and the steps each one takes. A request naming anything else is
#: refused before a single value in it is looked at.
#:
#: `install` is what the one-liner and the Installer window ask for: the
#: emulator with everything around it, a system to run on it where one was
#: asked for, and a configuration pointing at that system. It ends by starting
#: the machine, so what an installation leaves behind is a running NeXT rather
#: than a machine that needs rebooting first. Every step skips what it finds
#: already done, so asking for it twice changes nothing the second time.
JOBS = {
    "install": ("host", "tools", "archive", "emulator", "system",
                "configuration", "autologin", "quiet", "autostart", "sound",
                "start"),
    "update": ("archive", "newest-emulator"),
    # This tool replacing itself. Two steps because the second one is where the
    # service running the browser somebody is watching is stopped and started
    # underneath them, and a bar that covered both would sit still through the
    # only part they cannot see for themselves.
    UPDATE_TOOL: ("tool-package", "newest-tool"),
    "remove": ("no-autostart", "loud", "no-autologin", "no-emulator"),
    "fetch": ("host", "tools", "system"),
    "forget": ("no-system",),
    # A copy of a disk, and the same copy the other way. Both are one step,
    # because a copy of a file is one thing that either happens or does not.
    "back-up": ("copy",),
    "restore": ("put-back",),
}


# -- the machine this is running on ------------------------------------------


def run(command, seconds=COMMAND_SECONDS, heard=None):
    """Runs one command and answers what it said.

    @param command - The argument list. Never a string and never a shell, so
      there is nothing here that could be talked into running something else.
    @param seconds - How long to wait before giving up.
    @param heard - Called with each percentage apt reports on its status
      lines, as the command runs, or None for a command that is only waited
      for. The command has to be told to write those lines to its standard
      output, which `_apt_install` does.
    @returns str, its output with the whitespace taken off.
    @raises Refused where it failed, timed out or is not installed at all.

    apt is told there is nobody to ask, because a package putting a question up
    would wait for an answer from a console this has none of.
    """
    environment = dict(os.environ, DEBIAN_FRONTEND="noninteractive")
    try:
        if heard is None:
            answer = subprocess.run(command, capture_output=True, text=True,
                                    timeout=seconds, env=environment, check=False)
            code, said = answer.returncode, answer.stdout
        else:
            code, said = _streamed(command, seconds, environment, heard)
    except subprocess.TimeoutExpired as error:
        raise Refused("setup.took-too-long", command=command[0],
                      seconds=seconds) from error
    except OSError as error:
        raise Refused("setup.no-such-command", command=command[0]) from error

    if code != 0:
        raise Refused("setup.command-failed", command=command[0], code=code)
    return said.strip()


def _streamed(command, seconds, environment, heard):
    """Runs a command whose output is read as it comes, line by line.

    @param command - The argument list.
    @param seconds - How long it may take in all.
    @param environment - What it runs with.
    @param heard - Called with each percentage on an apt status line.
    @returns (int, str), its exit status and everything it wrote.
    @raises subprocess.TimeoutExpired where it took longer than `seconds`.

    The clock is a timer that ends the command, because a command that stops
    writing is exactly the one a wait on its next line would never see end.
    What it writes on its error stream is dropped, so that stream cannot fill
    and stop it whilst this reads the other.
    """
    process = subprocess.Popen(command, stdout=subprocess.PIPE,
                               stderr=subprocess.DEVNULL, text=True,
                               env=environment)
    ended = []

    def end():
        ended.append(True)
        process.kill()

    timer = threading.Timer(seconds, end)
    timer.start()
    said = []
    try:
        for line in process.stdout:
            said.append(line)
            percent = _apt_percent(line)
            if percent is not None:
                heard(percent)
        process.wait()
    finally:
        timer.cancel()
    if ended:
        raise subprocess.TimeoutExpired(command, seconds)
    return process.returncode, "".join(said)


def _apt_percent(line):
    """@returns float, how far dpkg has got by one apt status line, or None.

    @param line - One line apt wrote to its status descriptor. dpkg's own
      lines are `pmstatus:package:percent:what it is doing`; the download's
      lines start with `dlstatus` and are left out, because fetching is quick
      beside unpacking and a bar that ran to the end twice would say neither.
    """
    fields = line.split(":", 3)
    if len(fields) < 3 or fields[0] != "pmstatus":
        return None
    try:
        return float(fields[2])
    except ValueError:
        return None


def installed(package):
    """@returns bool - Whether dpkg has that package in place."""
    try:
        answer = subprocess.run(
            ["dpkg-query", "-W", "-f=${Status}", package],
            capture_output=True, text=True, check=False)
    except OSError:
        return False
    return "ok installed" in answer.stdout


def version_of(package):
    """@returns str - The version dpkg has in place, or None.

    What is running, as against what could be. Read from dpkg rather than from
    the archive, because a machine whose package lists are stale still knows
    exactly what is on it.
    """
    return _said(["dpkg-query", "-W", "-f=${Version}", package]) or None


def newest_of(package):
    """@returns str - What apt would install now, or None.

    Out of `apt-cache policy`, which reads the package lists as they stand. A
    machine that has not refreshed them answers with what it last saw, which is
    what apt itself would do, so this is what would actually be installed
    rather than what exists somewhere.
    """
    for line in _said(["apt-cache", "policy", package]).splitlines():
        said = line.strip()
        if said.startswith("Candidate:"):
            version = said.split(":", 1)[1].strip()
            return None if version in ("", "(none)") else version
    return None


def newer_than(version, other):
    """Whether `other` is a later version than `version`.

    @param version - What is installed.
    @param other - What the archive offers.
    @returns bool. False where either is missing, because an unknown version is
      not something to offer an update to.

    Asked of dpkg rather than compared as text. Debian's ordering is its own,
    and a string comparison would call 4.10 older than 4.9 and offer a
    downgrade as an update.
    """
    if not version or not other:
        return False
    try:
        answer = subprocess.run(
            ["dpkg", "--compare-versions", version, "lt", other],
            capture_output=True, check=False)
    except OSError:
        return False
    return answer.returncode == 0


def emulator():
    """What is on this machine and what the archive has.

    @returns dict with `here`, `version`, `newest` and `newer`, the last being
      whether there is anything to update to.

    Kept for a few seconds, because the Installer window asks twice a second
    whilst it is open and these three commands are the most expensive thing
    behind that route. What they answer changes when something is installed
    and at no other time, so a few seconds of memory costs nothing and saves a
    Pi real work.
    """
    global _REMEMBERED
    if _REMEMBERED and time.monotonic() - _REMEMBERED[0] < REMEMBER_SECONDS:
        return dict(_REMEMBERED[1])

    version = version_of(EMULATOR_PACKAGE)
    newest = newest_of(EMULATOR_PACKAGE)
    said = {
        "here": installed(EMULATOR_PACKAGE),
        "version": version,
        "newest": newest,
        "newer": newer_than(version, newest),
    }
    _REMEMBERED = (time.monotonic(), said)
    return dict(said)


def forget():
    """Throws that memory away, for a test and for the moment after a run.

    A run that installs or removes the emulator changes every one of those
    answers, and the window asks again the instant it finishes.
    """
    global _REMEMBERED
    _REMEMBERED = None


def _said(command):
    """@returns str - What a read-only command printed, or "" on any failure."""
    try:
        answer = subprocess.run(command, capture_output=True, text=True,
                                timeout=TIMEOUT_SECONDS, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return answer.stdout.strip() if answer.returncode == 0 else ""


class Owner:
    """Whoever owns the emulator, which is the user the tool runs as.

    Read from the owner file the package writes beside the tool's unit, because
    that is where it is decided. Nothing here is written by this program under
    root's name: a file in that person's home belongs to them.
    """

    def __init__(self, name):
        entry = pwd.getpwnam(name)
        self.name = name
        self.uid = entry.pw_uid
        self.gid = entry.pw_gid
        self.group = grp.getgrgid(entry.pw_gid).gr_name
        self.home = pathlib.Path(entry.pw_dir)

    @classmethod
    def from_unit(cls, unit=OWNER_FILE):
        """@returns Owner. @raises Refused where the owner file cannot be read.

        @param unit - The drop-in that names the user, as the package writes
          it beside the tool's unit.
        """
        try:
            found = re.search(r"^User=(.+)$", unit.read_text(encoding="utf-8"),
                              re.M)
        except OSError as error:
            raise Refused("setup.no-owner") from error
        if not found:
            raise Refused("setup.no-owner")
        try:
            return cls(found.group(1).strip())
        except KeyError as error:
            raise Refused("setup.no-owner") from error

    def owns(self, path):
        """Gives one path to them, and does not follow a link to do it."""
        os.chown(path, self.uid, self.gid, follow_symlinks=False)

    def directory(self, path):
        """Makes a directory and everything above it, theirs all the way."""
        missing = [place for place in [path, *path.parents]
                   if not place.exists()]
        for place in reversed(missing):
            place.mkdir(mode=0o755)
            self.owns(place)
        return missing

    def write(self, path, text, mode=0o644):
        """Writes a file of theirs, replacing it whole."""
        path.write_text(text, encoding="utf-8")
        path.chmod(mode)
        self.owns(path)


# -- what it says whilst it works --------------------------------------------


class Work:
    """One run, and what it has done so far.

    @param job - What was asked for, which is a key of JOBS.
    @param steps - The names of the steps it takes, in order.
    @param owner - Who owns the emulator.
    @param system - The System to put on the machine, or None.
    @param machine - The Machine a fresh configuration describes.
    @param settings - The tool's own configuration, read with that person's
      home, so both halves look in the same places.
    @param into - Where to write the progress, which is root's own directory.

    Everything a step needs is here, and the record of what to undo is here as
    well, because a failure in the eighth step has to reverse the seven before
    it in the world they left behind.
    """

    def __init__(self, job, steps, owner, system, machine, settings=None,
                 backup=None, into=OUR_DIRECTORY):
        self.job = job
        self.steps = steps
        self.owner = owner
        self.system = system
        self.machine = machine
        self.settings = settings
        #: Which copy is being put back, by the name it has in the folder
        #: copies are kept in. Nothing else in a request is a file name, and
        #: this one is matched against that folder's listing rather than joined
        #: onto a path.
        self.backup = backup
        #: Where this run put the package it downloaded of this tool itself, or
        #: None. Made by the step that fetches and removed by the step that
        #: installs, and on the record of what to undo as well, so a run that
        #: fails between the two leaves nothing behind either.
        self.tool = None
        self.into = into
        self.done = 0
        self.step = None
        self.part = None
        self.failed = None
        self.undone = []
        #: Which steps actually did something, as against the ones that found
        #: their work already done and skipped. A run where every step skips is
        #: right and is over in a second, and without this the window can only
        #: say "finished" to somebody who saw nothing happen.
        self.changed = []
        self._how = []
        self._said_at = 0.0
        self.started_at = time.time()
        self.finished_at = None
        self.ok = None

    # -- the record --------------------------------------------------------

    def undoes(self, how):
        """Records how to reverse what the step now running just did.

        @param how - A callable taking nothing. Recorded whilst the step is
          running rather than afterwards, so a step that fails half way through
          still reverses the half it managed.

        A step that records nothing is a step that found its work already done,
        so this is also what says which steps did anything at all.
        """
        self._how.append((self.step, how))
        self.did()

    def did(self):
        """Records that the step now running changed something it cannot undo.

        For the one step whose work is not a thing to put back: a machine that
        was switched on cannot be switched off again by a failure in a later
        step, and pretending otherwise would take somebody's running machine
        away. What is left is the other half of `undoes`, which is saying that
        this step did something at all.
        """
        if self.step not in self.changed:
            self.changed.append(self.step)

    def reverse(self):
        """Walks the record backwards, so each step is reversed in a world that
        still looks the way it did when that step ran."""
        for step, how in reversed(self._how):
            try:
                how()
            except OSError:
                continue
            if step not in self.undone:
                self.undone.append(step)
        self._how = []

    # -- what it is doing --------------------------------------------------

    def at(self, step, done):
        """Moves to a step and says so."""
        self.step = step
        self.done = done
        self.part = None
        self.say(force=True)

    def through(self, done, of, doing):
        """How far through something long, such as a download or an unpack.

        @param done - Bytes so far.
        @param of - Bytes in total, or 0 where nobody knows.
        @param doing - What is being done, as a name the browser says in words:
          one step can fetch, unpack and then move, and a bar on its own says
          none of that.

        Rate limited, because a chunk of a quarter of a megabyte arrives many
        times a second and the progress file would be rewritten for each. The
        first of each thing is written whatever the clock says, so that a
        download shows as having started rather than as a step with nothing
        happening in it.
        """
        beginning = self.part is None or self.part["doing"] != doing
        self.part = {"done": done, "of": of, "doing": doing}
        self.say(force=beginning)

    def say(self, force=False):
        """Writes the progress, as a whole file replaced at once.

        Replaced rather than appended to, so a browser reading it never sees
        half a record. Failing to write it is not worth stopping the work for:
        what is lost is being able to watch, and the machine is still being set
        up.
        """
        now = time.time()
        if not force and now - self._said_at < SAY_EVERY_SECONDS:
            return
        self._said_at = now
        try:
            self.into.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                    "w", dir=self.into, delete=False, encoding="utf-8") as file:
                json.dump(self.reading(), file, ensure_ascii=False, indent=2)
                scratch = pathlib.Path(file.name)
            scratch.chmod(0o644)
            scratch.replace(self.into / PROGRESS)
        except OSError:
            pass

    def reading(self):
        """@returns dict - Everything the tool shows about this run."""
        return {
            "do": self.job,
            "system": self.system.identifier if self.system else None,
            "machine": self.machine.identifier if self.machine else None,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "ok": self.ok,
            "step": self.step,
            "done": self.done,
            "of": len(self.steps),
            "part": self.part,
            "failed": self.failed,
            "undone": list(self.undone),
            "changed": list(self.changed),
        }

    def ends(self, ok, failure=None):
        """Closes the record, whichever way it went."""
        self.ok = ok
        self.failed = failure
        self.finished_at = time.time()
        self.part = None
        self.say(force=True)


# -- the steps ---------------------------------------------------------------


def _host(work):
    """Refuses a machine the emulator's package would not fit."""
    architecture = run(["dpkg", "--print-architecture"])
    if architecture != ARCHITECTURE:
        raise Refused("setup.wrong-architecture", found=architecture,
                      wanted=ARCHITECTURE)
    release = _release()
    if release != RELEASE:
        raise Refused("setup.wrong-release", found=release or "?",
                      wanted=RELEASE)


def _release():
    """@returns str - What Debian release this is, or "" where it will not say."""
    try:
        text = pathlib.Path("/etc/os-release").read_text(encoding="utf-8")
    except OSError:
        return ""
    found = re.search(r"^VERSION_CODENAME=(.+)$", text, re.M)
    return found.group(1).strip().strip('"') if found else ""


def _tools(work):
    """The compositor, the unpacker and the two tools that reach the emulator."""
    _packages(work, TOOLS)


def _sound(work):
    """Sends sound to a speaker rather than to HDMI, and loudly enough to hear."""
    _packages(work, SOUND)

    if SOUND_CONFIGURATION.exists():
        return
    SOUND_CONFIGURATION.parent.mkdir(parents=True, exist_ok=True)
    SOUND_CONFIGURATION.write_text(
        "# A speaker plugged into this machine starts loud enough to be heard.\n"
        "#\n"
        "# The stock value is 0.064, which is 40 per cent on a linear scale,\n"
        "# and NeXTSTEP's own sounds peak at about a third of full scale on top\n"
        "# of that. The two together are inaudible on a small speaker.\n"
        "#\n"
        "# This applies the first time a device is seen. After that the volume\n"
        "# that was set is remembered per device.\n"
        "\n"
        "wireplumber.settings = {\n"
        "  device.routes.default-sink-volume = %s\n"
        "}\n" % VOLUME, encoding="utf-8")
    work.undoes(lambda: SOUND_CONFIGURATION.unlink(missing_ok=True))


def _packages(work, wanted):
    """Installs whichever of these are not already here, and records the undo.

    @param work - The run.
    @param wanted - The package names.

    Only what was missing is recorded, so undoing never takes away something
    the machine already had.
    """
    missing = [package for package in wanted if not installed(package)]
    if not missing:
        return
    run(["apt-get", "update", "-qq"])
    _apt_install(work, missing)
    work.undoes(lambda: run(["apt-get", "remove", "-y", "-qq", *missing]))


def _apt_install(work, arguments):
    """Installs with apt, and says how far dpkg has got whilst it does.

    @param work - The run, whose progress carries the percentage.
    @param arguments - What follows `apt-get install -y -qq`: package names,
      and any option that goes with them.

    A step that installs a hundred packages takes minutes, and without this
    the window and the one-liner show a step that looks stuck. apt writes its
    status lines to the descriptor it is given, and standard output is the one
    this reads.
    """
    run(["apt-get", "-o", "APT::Status-Fd=1", "install", "-y", "-qq", *arguments],
        heard=lambda percent: work.through(round(percent), 100, INSTALLING))


def _archive(work):
    """The Window Maker Live source, pinned so that only Previous comes from it."""
    if not REPOSITORY_KEY.exists():
        REPOSITORY_KEY.parent.mkdir(parents=True, exist_ok=True)
        _fetched("%s/%s.asc" % (REPOSITORY_URL, REPOSITORY_HOST),
                 REPOSITORY_KEY, work, (REPOSITORY_HOST,))
        REPOSITORY_KEY.chmod(0o644)
        work.undoes(lambda: REPOSITORY_KEY.unlink(missing_ok=True))

    if not REPOSITORY_SOURCE.exists():
        REPOSITORY_SOURCE.write_text(
            "Types: deb\n"
            "URIs: %s\n"
            "Suites: %s\n"
            "Components: main\n"
            "Signed-By: %s\n" % (REPOSITORY_URL, REPOSITORY_SUITE,
                                 REPOSITORY_KEY), encoding="utf-8")
        work.undoes(lambda: REPOSITORY_SOURCE.unlink(missing_ok=True))

    if not REPOSITORY_PINS.exists():
        # The archive carries more than Previous, and without this it could
        # replace packages that belong to Debian. -1 blocks everything, and the
        # emulator is let back in at the ordinary priority.
        REPOSITORY_PINS.write_text(
            "Package: *\n"
            "Pin: origin %s\n"
            "Pin-Priority: -1\n"
            "\n"
            "Package: %s\n"
            "Pin: origin %s\n"
            "Pin-Priority: 500\n" % (REPOSITORY_HOST, EMULATOR_PACKAGE,
                                     REPOSITORY_HOST), encoding="utf-8")
        work.undoes(lambda: REPOSITORY_PINS.unlink(missing_ok=True))


def _emulator(work):
    """Previous itself, left alone where it is already here."""
    if installed(EMULATOR_PACKAGE):
        return
    run(["apt-get", "update", "-qq"])
    _apt_install(work, [EMULATOR_PACKAGE])
    work.undoes(lambda: run(["apt-get", "remove", "-y", "-qq",
                             EMULATOR_PACKAGE]))


def _newest_emulator(work):
    """The newest Previous the archive has.

    Nothing is recorded to undo. Going back to the version that was here would
    mean holding a copy of it, and apt has no idea where the old one went.
    """
    run(["apt-get", "update", "-qq"])
    _apt_install(work, ["--only-upgrade", EMULATOR_PACKAGE])


def _tool_package(work):
    """Fetches the newest release of this tool, and refuses anything else.

    Nothing about the machine changes here. What this leaves is one file in a
    directory of root's own making, checked three ways, and the step after it is
    the one that acts on it.

    The check is the point of the step. `apt-get` is about to be pointed at this
    file as root, so what it is has to be settled first: the size and the digest
    GitHub states for that asset, and then the package's own control file, which
    has to say this is `previously` at the version somebody was offered. A digest
    alone proves the bytes are the bytes GitHub served, and those last two are
    what prove that what GitHub served is this tool at that version.
    """
    newest = _the_newest_tool()
    here = version_of(release.PACKAGE)
    if not newer_than(here, newest["version"]):
        raise Refused("setup.tool-is-current", version=here or "?")

    work.tool = pathlib.Path(tempfile.mkdtemp(prefix="previously-update."))
    work.undoes(lambda where=work.tool: shutil.rmtree(str(where),
                                                      ignore_errors=True))

    package = work.tool / release.ASSET
    _fetched(newest["url"], package, work, release.HOSTS,
             fetching.Expecting(release.ASSET, newest["size"],
                                newest["digest"], release.ALGORITHM))

    # The whole of it, because it is all here by now: what changes is what is
    # being done to it, and a bar that fell back to nothing to say so would read
    # as a download starting again.
    work.through(newest["size"], newest["size"], CHECKING)
    _the_package_asked_for(package, newest["version"])


def _newest_tool(work):
    """Installs the package the step before fetched, replacing this tool.

    This is where the service the browser is talking to is stopped and started
    again, because the package's own maintainer scripts do that. The request
    that asked for this was answered long before, and the page is watching the
    file this run writes rather than waiting for a reply.

    Nothing is recorded to undo. Going back would mean holding a copy of the
    package that is here now, and a failure leaves that one installed and
    running, which is the safe direction and the one `install.sh --update-admin`
    takes for the same reason.

    The directory goes whichever way this ends, and the reversal record holds
    the same removal, so nothing is left on the card by a run that stopped
    between the two steps.
    """
    if work.tool is None:
        raise Refused("setup.no-package-to-install")

    package = work.tool / release.ASSET
    work.through(0, 0, INSTALLING)
    try:
        run(["apt-get", "install", "-y", "-qq", str(package)])
    finally:
        shutil.rmtree(str(work.tool), ignore_errors=True)
    work.did()


def _the_newest_tool():
    """@returns dict as `release.look` describes it.

    @raises Refused where GitHub could not be asked or said something this does
      not understand. Asked here rather than taken from the service, because the
      service is what a browser talks to and this is the half that has to be
      sure: an address it was handed would be an address somebody else chose.
    """
    try:
        return release.look()
    except release.Unreachable as error:
        raise Refused("setup.cannot-ask-about-releases") from error


def _the_package_asked_for(package, version):
    """Refuses a package that is not this tool at the version that was offered.

    @param package - pathlib.Path of the file that was downloaded.
    @param version - What the release is tagged as.
    @raises Refused where the control file says anything else.

    Read with `dpkg-deb`, so the answer comes out of the file rather than out of
    its name. A release that carried somebody else's package under the name this
    looks for would otherwise be installed on the strength of the digest that
    same release stated for it.
    """
    named = run(["dpkg-deb", "-f", str(package), "Package"], TIMEOUT_SECONDS)
    if named != release.PACKAGE:
        raise Refused("setup.not-our-package", found=named or "?")

    carries = run(["dpkg-deb", "-f", str(package), "Version"], TIMEOUT_SECONDS)
    if carries != version:
        raise Refused("setup.not-that-version", found=carries or "?",
                      wanted=version)


def _no_emulator(work):
    """Takes Previous away, along with what it brought, and its source with it.

    What it brought is whatever apt installed for its sake and nothing else:
    autoremove only takes packages that were pulled in as dependencies and that
    nothing left on the machine still wants. The four tools were asked for by
    name, so apt holds them as somebody's own choice and leaves them, which is
    what should happen: something else here may use ImageMagick or 7zip by now.
    """
    if installed(EMULATOR_PACKAGE):
        run(["apt-get", "purge", "-y", "-qq", EMULATOR_PACKAGE])
        run(["apt-get", "autoremove", "--purge", "-y", "-qq"])
    for path in (REPOSITORY_PINS, REPOSITORY_SOURCE, REPOSITORY_KEY):
        path.unlink(missing_ok=True)


def _system(work):
    """Fetches a system and puts its disk where the disks live.

    Skipped where that system is already here, and where none was asked for at
    all, which is how the emulator can be installed on its own.
    """
    if work.system is None:
        return

    disks = work.settings.disks
    if systems.disk_in(disks, work.system) is not None:
        return

    free = systems.room_beside(disks)
    if free is not None and free < systems.ROOM_BYTES:
        raise Refused("setup.no-room", free=free, needed=systems.ROOM_BYTES,
                      name=work.system.name)

    for made in work.owner.directory(disks):
        work.undoes(lambda place=made: place.rmdir())

    unpacked = disks / systems.disk_name(work.system)
    scratch = pathlib.Path(tempfile.mkdtemp(dir=str(disks)))
    try:
        archive = scratch / work.system.file
        _fetched(systems.address(work.system), archive, work,
                 systems.ARCHIVE_HOSTS, systems.expected(work.system))
        _unpacked(archive, scratch, work)
        shutil.move(str(_disk_among(scratch, work.system)), str(unpacked))
    finally:
        shutil.rmtree(scratch, ignore_errors=True)

    work.owner.owns(unpacked)
    unpacked.chmod(0o644)
    work.undoes(lambda: unpacked.unlink(missing_ok=True))


def _no_system(work):
    """Takes one system's disk away, and never the one the machine boots.

    Which disk the machine boots is one line in `previous.cfg`, so that file is
    read rather than guessed at. A request to remove the system in use is
    refused whole and nothing is touched.
    """
    if work.system is None:
        raise Refused("setup.no-system-named")

    disks = work.settings.disks
    disk = systems.disk_in(disks, work.system)
    if disk is None:
        raise Refused("setup.system-is-not-here", name=work.system.name)

    if _in_use(work.settings.previous_config, disk):
        raise Refused("setup.system-in-use", name=work.system.name)

    if disk.parent != disks:
        # The layout of a disk unpacked straight from its archive: the disk
        # inside a folder named after the archive, beside the ROM images and
        # the Windows binary that came with it. All of it goes, because all of
        # it came from that one archive.
        shutil.rmtree(disk.parent, ignore_errors=True)
    else:
        disk.unlink(missing_ok=True)


def _in_use(configuration, disk):
    """@returns bool - Whether previous.cfg boots from that disk."""
    try:
        text = configuration.read_text(encoding="utf-8")
    except OSError:
        return False
    return str(disk) in text


def _copy(work):
    """Copies a disk, so that what is on it can be got back.

    Only with the guest shut down. A copy taken whilst NeXTSTEP is writing is a
    torn file system: it looks like a disk and fails on the first boot in a way
    nobody can debug.
    """
    if work.system is None:
        raise Refused("setup.no-system-named")
    if _the_guest_is_running():
        raise Refused("setup.machine-is-running")

    disk = systems.disk_in(work.settings.disks, work.system)
    if disk is None:
        raise Refused("setup.system-is-not-here", name=work.system.name)

    size = disk.stat().st_size
    free = systems.room_beside(work.settings.disks)
    if free is not None and free < size + systems.SPARE_BYTES:
        raise Refused("setup.no-room", name=work.system.name, free=free,
                      needed=size + systems.SPARE_BYTES)

    where = systems.backups_in(work.settings.disks)
    for made in work.owner.directory(where):
        work.undoes(lambda place=made: place.rmdir())

    copy = where / systems.a_copy_of(work.system, datetime.datetime.now())
    work.undoes(lambda: copy.unlink(missing_ok=True))
    _copied_across(disk, copy, work)
    work.owner.owns(copy)
    copy.chmod(0o644)


def _put_back(work):
    """Writes a copy back over the disk it was made from.

    The same two conditions, and one more: the copy has to be one that is
    actually in the folder copies are kept in. The name arrives from a browser,
    so it is matched against what is there rather than joined onto a path.
    """
    if work.system is None:
        raise Refused("setup.no-system-named")
    if _the_guest_is_running():
        raise Refused("setup.machine-is-running")

    copy = _the_copy_named(work)
    disk = systems.disk_in(work.settings.disks, work.system)
    if disk is None:
        raise Refused("setup.system-is-not-here", name=work.system.name)

    # Beside the disk and moved into place, so a copy that stops half way
    # through leaves the disk that was there rather than half of each.
    coming = disk.with_name(disk.name + ".coming-back")
    work.undoes(lambda: coming.unlink(missing_ok=True))
    _copied_across(copy, coming, work)
    work.owner.owns(coming)
    coming.chmod(0o644)
    coming.replace(disk)


def _the_copy_named(work):
    """Which copy the request meant.

    @param work - The run, whose `backup` is the name that arrived.
    @returns pathlib.Path
    @raises Refused where nothing of that name is in the folder.

    Matched against the listing rather than joined onto a path, so a name
    carrying separators or dots asks for a file that is not in the answer and
    is refused. Nothing that arrives from a browser reaches the filesystem as a
    path here, any more than anywhere else in this program.
    """
    for path, _ in systems.copies_in(work.settings.disks):
        if path.name == work.backup:
            return path
    raise Refused("setup.no-such-copy")


def _copied_across(source, into, work):
    """Copies one file, saying how far it has got.

    @param source - pathlib.Path to read.
    @param into - pathlib.Path to write.
    @param work - The run, which is told how far through this is.
    @raises Refused where it could not be done.

    Two gigabytes on a card, so it is minutes and the window says so. Written
    in chunks rather than through shutil, because what a person watching wants
    is the figure and shutil has nowhere to put one.
    """
    total = source.stat().st_size
    done = 0
    try:
        with open(source, "rb") as reading, open(into, "wb") as writing:
            while True:
                chunk = reading.read(COPY_BYTES)
                if not chunk:
                    break
                writing.write(chunk)
                done += len(chunk)
                work.through(done, total, COPYING)
    except OSError as error:
        raise Refused("setup.cannot-copy",
                      name=work.system.name if work.system else "?") from error


def _the_guest_is_running():
    """Whether the emulator is up.

    @returns bool

    Asked through `kiosk.py`, which is the one place that question is answered,
    and imported here rather than at the top because that module writes the
    request this program reads and importing it back at load time would be a
    circle. One import inside one function is cheaper than a second answer to
    the same question.
    """
    from . import kiosk
    return kiosk.emulator_is_running()


def _configuration(work):
    """The emulator's configuration, pointing at the system that is here.

    Left exactly as it stands where there is one already. A machine somebody
    has built is theirs, and this is the step that would overwrite it.
    """
    pictures = files.picture_directory(work.settings.documents)
    if pictures is not None and not pictures.is_dir():
        for made in work.owner.directory(pictures):
            work.undoes(lambda place=made: place.rmdir())

    configuration = work.settings.previous_config
    if configuration.exists():
        return
    if work.system is None:
        return

    disk = systems.disk_in(work.settings.disks, work.system)
    if disk is None:
        raise Refused("setup.system-is-not-here", name=work.system.name)

    for made in work.owner.directory(configuration.parent):
        work.undoes(lambda place=made: place.rmdir())
    work.owner.write(configuration, _written(work.machine, disk))
    work.undoes(lambda: configuration.unlink(missing_ok=True))


def _written(machine, disk):
    """The configuration a fresh machine gets.

    @param machine - The Machine it describes.
    @param disk - pathlib.Path of the disk it boots.
    @returns str

    Only the keys that differ from what Previous writes by default, plus the
    machine itself. Everything else it fills in the first time it exits,
    including the path to the ROM it boots from, which its own package
    installs.
    """
    sections = {
        "ConfigDialog": {"bShowConfigDialogAtStartup": "FALSE"},
        "Screen": {"bFullScreen": "TRUE", "bShowStatusbar": "FALSE",
                   "bShowTitlebar": "FALSE"},
        "Boot": {"nBootDevice": "1", "bVisible": "FALSE"},
        "HardDisk": {"szImageName0": str(disk), "nDeviceType0": "1",
                     "bDiskInserted0": "TRUE", "bWriteProtected0": "FALSE"},
    }
    sections.update(machines.settings_for(machine))
    return "".join(
        "[%s]\n%s\n" % (name, "".join("%s = %s\n" % pair
                                      for pair in keys.items()))
        for name, keys in sections.items())


def _autologin(work):
    """Logs in on the text console without asking."""
    if AUTOLOGIN.exists():
        return
    run(["raspi-config", "nonint", "do_boot_behaviour", "B2"])
    work.undoes(_no_autologin_now)


def _no_autologin(work):
    """Puts the console back to asking who is there."""
    _no_autologin_now()


def _no_autologin_now():
    run(["raspi-config", "nonint", "do_boot_behaviour", "B1"])
    AUTOLOGIN.unlink(missing_ok=True)


def _quiet(work):
    """Silences the five things that draw on the screen before NeXTSTEP does.

    The firmware splash, the kernel logo and its messages, systemd's status
    list, the blinking cursor of the text console, and the login banner. The
    banner is the one that outlasts the boot: the console waits for the
    emulator rather than exiting, so nothing overwrites what login printed.
    """
    _kept_quiet(CONFIG_TXT, NO_SPLASH, work)
    # The kernel's own logo, because a stock command line already carries
    # `quiet` and would read as done before anything had been changed.
    _kept_quiet(CMDLINE, "logo.nologo", work)

    hushlogin = work.owner.home / HUSHLOGIN
    if not hushlogin.exists():
        work.owner.write(hushlogin, "")
        work.undoes(lambda: hushlogin.unlink(missing_ok=True))

    written = AUTOLOGIN.read_text(encoding="utf-8") if AUTOLOGIN.exists() else ""
    if "--noissue" not in written and written:
        AUTOLOGIN.write_text(
            written.replace(
                "agetty --autologin", "agetty --noissue --autologin"),
            encoding="utf-8")
        run(["systemctl", "daemon-reload"])


def _kept_quiet(path, already, work):
    """Changes one of the two boot files, keeping a copy of what it was.

    @param path - The file.
    @param already - Text that says this has been done before.
    @param work - The run, which records how to put the copy back.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        # Not a Raspberry Pi, or a boot partition that is not mounted. The
        # screen then shows what it shows, which is worth saying nothing about:
        # everything else here still works.
        return
    if already in text:
        return

    backup = path.with_suffix(path.suffix + BACKUP)
    shutil.copy2(path, backup)
    work.undoes(lambda: shutil.move(str(backup), str(path)))

    if path == CONFIG_TXT:
        path.write_text(text.rstrip("\n") + "\n%s\n" % NO_SPLASH,
                        encoding="utf-8")
    else:
        path.write_text(_quietened(text), encoding="utf-8")


def _quietened(text):
    """The kernel's command line, with the console moved off the screen.

    @param text - What the file holds.
    @returns str

    The console is moved rather than added, because two `console=` arguments
    would leave the kernel writing to tty1 as well, which is the one on screen.
    """
    line = text.splitlines()[0] if text.strip() else ""
    if "console=tty1" in line:
        line = line.replace("console=tty1", "console=tty3")
    elif "console=tty" not in line:
        line = "console=tty3 " + line
    return " ".join([line.strip(), *QUIET_ARGUMENTS]) + "\n"


def _loud(work):
    """Puts both boot files back, where a copy of them is still here."""
    for path in (CMDLINE, CONFIG_TXT):
        backup = path.with_suffix(path.suffix + BACKUP)
        if backup.exists():
            shutil.move(str(backup), str(path))
    (work.owner.home / HUSHLOGIN).unlink(missing_ok=True)


def _autostart(work):
    """Hands the first console to the emulator, and leaves SSH alone.

    Fenced by markers, so taking it out again leaves whatever else the file
    holds.

    A block that is already there and no longer says what this version writes
    is replaced rather than left. It is generated, so a machine set up a year
    ago carries a year-old console, and the one change that matters most is
    the one nobody would notice: the line that writes down a crash.
    """
    profile = work.owner.home / PROFILE
    text = profile.read_text(encoding="utf-8") if profile.exists() else ""
    wanted = _autostart_block(work.owner)
    if AUTOSTART_OPENS in text:
        if _the_block_in(text) == wanted.strip("\n"):
            return
        was = text
        work.owner.write(profile, _without_the_block(text) + wanted)
        work.undoes(lambda: work.owner.write(profile, was))
        return

    work.owner.write(profile, text + wanted)
    work.undoes(lambda: _without_autostart(profile))


def _the_block_in(text):
    """@returns str - The fenced block as it stands, markers and all, or ""."""
    opens = text.find(AUTOSTART_OPENS)
    closes = text.find(AUTOSTART_CLOSES)
    if opens == -1 or closes == -1:
        return ""
    return text[opens:closes + len(AUTOSTART_CLOSES)]


def _without_the_block(text):
    """@returns str - The same text with the fenced block taken out.

    The blank line in front of it goes too, because the block is written with
    one and replacing it twice would otherwise gain a line each time.
    """
    kept = []
    inside = False
    for line in text.splitlines(keepends=True):
        if line.strip() == AUTOSTART_OPENS:
            inside = True
            if kept and not kept[-1].strip():
                kept.pop()
        elif line.strip() == AUTOSTART_CLOSES:
            inside = False
        elif not inside:
            kept.append(line)
    return "".join(kept)


def _autostart_block(owner):
    """@returns str - What is added to the profile, markers and all.

    Every line of this, comments included, is what `install.sh
    --update-admin` writes, because replacing the tool from a shell brings the
    console up to date without asking for anything else. Either of the two
    may therefore have written a given machine's console, and both replace a
    block that no longer says what they write. A difference between them
    would therefore be the two rewriting each other for ever.

    `tests/test_setup.py` holds them together character for character.
    """
    return (
        "\n%s\n"
        "# Hand the first console to Previous. XDG_VTNR carries the number of the text\n"
        "# console and is set only where one is actually behind the login, so an SSH\n"
        "# session falls through and stays the way in once the screen is taken.\n"
        "#\n"
        "# The wait is how the admin tool stops and starts the emulator without any\n"
        "# privileges at all: it creates %s to hold it down and removes the\n"
        "# file to let it come back. Waiting rather than exiting matters twice. It keeps\n"
        "# the console from falling through to a shell prompt while the emulator is\n"
        "# held, and it avoids the race that stopping through systemd would have, since\n"
        "# this unit restarts itself the moment a session ends and would bring a fresh\n"
        "# emulator up underneath whatever stopped the last one.\n"
        "#\n"
        "# The file is on a tmpfs, so a board that has just booted never finds one and\n"
        "# always starts its emulator.\n"
        "#\n"
        "# The directory it runs in is where it writes a screen grab, and the admin tool\n"
        "# reads those and removes them. Its own rather than the home directory, so the\n"
        "# tool needs write access to that one directory and to nothing else of yours.\n"
        "#\n"
        "# An emulator that ends badly says so in one line, which the Raspberry Pi window\n"
        "# reads. It goes in the runtime directory because that is a tmpfs: the file is\n"
        "# gone at every boot, so whatever is in it happened since this board came up and\n"
        "# nothing has to work out when. The exit runs the session down exactly as exec\n"
        "# did, so the console never falls through to a prompt.\n"
        'if [ "$XDG_VTNR" = 1 ] && [ -z "$WAYLAND_DISPLAY" ]; then\n'
        "  clear\n"
        "  while [ -f %s ]; do sleep 2; done\n"
        "  mkdir -p %s\n"
        "  cd %s\n"
        "  cage -- /usr/bin/previous\n"
        "  status=$?\n"
        '  if [ "$status" -ne 0 ] && [ -d %s ]; then\n'
        '    printf "%%s %%s\\n" "$(date +%%s)" "$status" >> %s\n'
        "  fi\n"
        '  exit "$status"\n'
        "fi\n"
        "%s\n" % (AUTOSTART_OPENS, HOLD, HOLD,
                  owner.home / WORK_DIRECTORY,
                  owner.home / WORK_DIRECTORY,
                  RUNTIME, CRASHES, AUTOSTART_CLOSES))


def _no_autostart(work):
    """Gives the first console back to whoever logs in on it."""
    _without_autostart(work.owner.home / PROFILE)


def _without_autostart(profile):
    """Takes the fenced block out and leaves the rest of the file alone.

    The blank line that was put in front of the block goes with it, so adding
    the block and taking it away again leaves the file exactly as it was. A
    file that gains one empty line per installation is not left as it was.
    """
    try:
        text = profile.read_text(encoding="utf-8")
    except OSError:
        return
    profile.write_text(_without_the_block(text), encoding="utf-8")


def _start(work):
    """Starts the emulator, so an installation ends with a machine running.

    The console is what starts it: it logs itself in on the first text console
    and the profile written a step earlier runs Previous there. That console
    has been sitting at a login prompt since before any of this existed, so it
    is restarted to pick both of them up. Without this the machine is fully
    installed and shows nothing until somebody reboots it.

    The hold goes first, because the tool leaves that file behind when somebody
    switched the emulator off, and a console that finds it waits rather than
    starting anything.

    Left alone where the emulator is already running, since restarting the
    console under a running guest costs whatever that guest had not written.
    """
    if _the_guest_is_running():
        return
    pathlib.Path(HOLD).unlink(missing_ok=True)
    run(["systemctl", "restart", work.settings.kiosk_unit])
    work.did()


#: Every step there is, by the name a job names it with. The name is what the
#: browser says a sentence about, so one added here without a sentence beside
#: it shows on the screen as itself, which `tests/test_strings.py` refuses.
STEPS = {
    "host": _host,
    "tools": _tools,
    "archive": _archive,
    "emulator": _emulator,
    "newest-emulator": _newest_emulator,
    "no-emulator": _no_emulator,
    "tool-package": _tool_package,
    "newest-tool": _newest_tool,
    "system": _system,
    "no-system": _no_system,
    "configuration": _configuration,
    "autologin": _autologin,
    "no-autologin": _no_autologin,
    "quiet": _quiet,
    "loud": _loud,
    "autostart": _autostart,
    "no-autostart": _no_autostart,
    "sound": _sound,
    "start": _start,
    "copy": _copy,
    "put-back": _put_back,
}


# -- fetching ----------------------------------------------------------------


def _fetched(url, into, work, hosts, expecting=None):
    """Downloads one file, saying how far it has got.

    @param url - Where from.
    @param into - pathlib.Path to write.
    @param work - The run, which is told how far through this is.
    @param hosts - Which hosts this may reach, as `fetching.allowed` takes them.
      Checked on the address itself as well as on every redirect.
    @param expecting - A `fetching.Expecting` saying what the file has to turn
      out to be, or None where it is small enough that there is nothing to
      check.
    @raises Refused where it could not be fetched or is not what was expected.

    Redirects are followed and checked at every hop, because both places this
    fetches from answer a download by sending the caller somewhere else:
    archive.org to whichever node holds the item, and GitHub to the host its
    release assets are served from.
    """
    size = expecting.size if expecting else 0
    algorithm = expecting.algorithm if expecting else None
    digest = None
    try:
        with fetching.opened(url, hosts, FETCH_SECONDS) as answer:
            digest = _copied(answer, into, work, size, algorithm)
    except (urllib.error.URLError, OSError) as error:
        raise Refused("setup.cannot-fetch",
                      name=expecting.name if expecting else url) from error

    if expecting is None:
        return
    if into.stat().st_size != expecting.size or digest != expecting.digest:
        raise Refused("setup.not-what-was-expected", name=expecting.name)


def _copied(answer, into, work, size, algorithm=None):
    """Writes what a fetch is answering with, and answers with its digest.

    @param answer - The open answer to read.
    @param into - pathlib.Path to write.
    @param work - The run, which is told how far through this is.
    @param size - How many bytes are expected, or 0 where nobody knows, in which
      case nothing is reported: a bar with no end is worse than no bar.
    @param algorithm - Which digest to take, because the two places this fetches
      from state different ones. None where the caller has nothing to check the
      file against, and then none is taken.
    @returns str, the digest as hex, or None where none was asked for.
    """
    running = hashlib.new(algorithm) if algorithm else None
    done = 0
    with open(into, "wb") as file:
        while True:
            chunk = answer.read(CHUNK_BYTES)
            if not chunk:
                break
            file.write(chunk)
            if running is not None:
                running.update(chunk)
            done += len(chunk)
            if size:
                work.through(done, size, FETCHING)
    return running.hexdigest() if running is not None else None


def _unpacked(archive, into, work):
    """Unpacks a system archive, saying how far it has got.

    @param archive - pathlib.Path of the .7z.
    @param into - Where to unpack it.
    @param work - The run.
    @raises Refused where the unpacker failed.

    How far is measured by how much has been written rather than by reading
    what 7z prints, because what it prints is a progress bar meant for a
    terminal and a disk that is two gigabytes is a number this already knows.
    """
    unpacking = subprocess.Popen(
        ["7z", "x", "-y", "-bso0", "-bsp0", "-o" + str(into), str(archive)],
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    while unpacking.poll() is None:
        work.through(_written_into(into) - archive.stat().st_size,
                     systems.UNPACKED_BYTES, UNPACKING)
        time.sleep(SAY_EVERY_SECONDS)
    if unpacking.returncode != 0:
        raise Refused("setup.cannot-unpack",
                      name=work.system.name if work.system else "?")


def _written_into(directory):
    """@returns int - How many bytes everything under a directory comes to."""
    total = 0
    for path in directory.rglob("*"):
        try:
            if path.is_file():
                total += path.stat().st_size
        except OSError:
            continue
    return total


def _disk_among(unpacked, system):
    """The disk image an archive carried.

    @param unpacked - Where it was unpacked to.
    @param system - Which system it is, for the complaint.
    @returns pathlib.Path
    @raises Refused where there is nothing in it big enough to be a disk.

    The largest file, because these archives also carry the ROM images, a
    Windows binary and a text file, and none of those comes near half a
    gigabyte.
    """
    found = [path for path in unpacked.rglob("*")
             if path.is_file() and path.stat().st_size >= systems.SMALLEST_DISK_BYTES]
    if not found:
        raise Refused("setup.no-disk-in-the-archive", name=system.name)
    return max(found, key=lambda path: path.stat().st_size)


# -- the request -------------------------------------------------------------


def taken(path):
    """Reads the request and takes it away, whatever it turns out to be.

    @param path - Where the tool leaves it.
    @returns dict, or None where there was nothing readable there.

    Taken away first, so that the path unit watching for it does not start this
    again the moment it finishes.

    Opened without following a link and checked before it is read, because the
    directory it sits in belongs to an unprivileged user. A link left there
    would otherwise have root read whatever it pointed at, and this program
    reports what it could not understand.
    """
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    except OSError:
        return None
    try:
        about = os.fstat(descriptor)
        if not stat.S_ISREG(about.st_mode) or about.st_size > LARGEST_REQUEST:
            return None
        text = os.read(descriptor, LARGEST_REQUEST).decode("utf-8", "replace")
    except OSError:
        return None
    finally:
        os.close(descriptor)
        try:
            os.unlink(path)
        except OSError:
            pass

    try:
        found = json.loads(text)
    except ValueError:
        return None
    return found if isinstance(found, dict) else None


def asked_for(request):
    """What a request means, or a refusal.

    @param request - What was read.
    @returns (job, steps, system, machine, backup)
    @raises Refused where any of the names is not one this knows.

    Three of the four are keys of a table that ships with this package, so
    nothing in a request is a path, a URL, a command or a number. The fourth is
    the name of a copy, and it is matched against the listing of the folder
    copies are kept in when the step runs, rather than joined onto a path here.
    """
    job = request.get("do")
    if job not in JOBS:
        raise Refused("setup.no-such-job")

    named = request.get("system")
    system = None
    if named is not None:
        system = systems.find(named)
        if system is None:
            raise Refused("setup.no-such-system")

    machine = machines.find(request.get("machine") or DEFAULT_MACHINE)
    if machine is None:
        raise Refused("setup.no-such-machine")

    backup = request.get("backup")
    if backup is not None and (not isinstance(backup, str)
                               or len(backup) > LONGEST_NAME):
        raise Refused("setup.no-such-copy")

    return job, tuple(JOBS[job]), system, machine, backup


# -- the run -----------------------------------------------------------------


def carry_out(work):
    """Takes every step of a job, and reverses them all where one fails.

    @param work - The run.
    @returns bool, whether it finished.
    """
    for done, name in enumerate(work.steps, start=1):
        work.at(name, done)
        try:
            STEPS[name](work)
        except Refused as refusal:
            work.reverse()
            work.ends(False, {"step": name, **refusal.told})
            return False
    work.ends(True)
    return True


def main(argv=None):
    """Reads one request and carries it out.

    @param argv - Ignored. There are no options: what to do arrives in the
      request, and a program root starts is not one to give a command line to.
    @returns int, the exit status.

    The configuration is read twice, and the second time with the owner's home,
    because a path in it written as `~/nextstep` means their home and this runs
    as root. The first reading is only for the runtime directory, which is
    `/run/previously` and is also written into the path unit that starts this.
    """
    request = taken(Settings.load().runtime_directory / REQUEST)
    if request is None:
        # Nothing to do. The path unit fires on a file appearing, and a file
        # that is gone or unreadable by the time this runs is not an error
        # worth a failed unit in the journal.
        return 0

    try:
        job, steps, system, machine, backup = asked_for(request)
    except Refused as refusal:
        Work("?", (), None, None, None).ends(False, dict(refusal.told))
        return 1

    try:
        owner = Owner.from_unit()
    except Refused as refusal:
        Work(job, steps, None, system, machine).ends(False, dict(refusal.told))
        return 1

    work = Work(job, steps, owner, system, machine,
                Settings.load(home=owner.home), backup)
    return 0 if carry_out(work) else 1


if __name__ == "__main__":
    sys.exit(main())
