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

The work itself is the nine steps `install.sh` takes, in the same order, each
of them skipping what it finds already done, plus the sound that script does
tenth. Every step that changes something records how to undo exactly that, and
a failure walks the record backwards, which is what that script does too.

`install.sh` keeps its own copy of those steps for now, because it is the way
in on a machine that has no admin tool yet and therefore cannot ask for any of
this. Making it ask, so that there is one implementation rather than two, waits
until this one has set a real machine up.
"""

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
import time
import urllib.error
import urllib.parse
import urllib.request

from . import files, machines, systems
from .answers import told
from .settings import Settings

#: What the tool calls the request, inside its own runtime directory.
#: `previously-setup.path` watches for this name and starts this program.
REQUEST = "setup"

#: The most a request may be. Everything one can say is three names, so
#: anything past this is not the tool talking.
LARGEST_REQUEST = 4096

#: Where this writes what it is doing. Its own directory rather than the tool's,
#: and that is the point: the tool's runtime directory belongs to an
#: unprivileged user, so a file root wrote there could be replaced by a link to
#: somewhere else between one write and the next. This one is root's, made by
#: `RuntimeDirectory=` in the unit, and the tool only reads it.
OUR_DIRECTORY = pathlib.Path("/run/previously-setup")
PROGRESS = "progress.json"

#: Where the unit that decides who owns the emulator lives. The user is read
#: from there rather than named again here, because that unit is where it is
#: decided and a second copy would be a second answer.
SERVICE_UNIT = pathlib.Path("/lib/systemd/system/previously.service")

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
#: which is what `install.sh` writes. Where the disks live, where that
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

#: The file the tool creates to hold the emulator down, which the autostart
#: below waits on.
HOLD = "/run/previously/hold"

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

#: How long to wait for one command. An unpack of two gigabytes on a Pi is the
#: long one, and a step that hangs is worse than one that fails because nothing
#: says so.
COMMAND_SECONDS = 1800


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
#: `install` is the whole of `install.sh`: the emulator with everything around
#: it, a system to run on it where one was asked for, and a configuration
#: pointing at that system. Every step skips what it finds already done, so
#: asking for it twice changes nothing the second time.
JOBS = {
    "install": ("host", "tools", "archive", "emulator", "system",
                "configuration", "autologin", "quiet", "autostart", "sound"),
    "update": ("archive", "newest-emulator"),
    "remove": ("no-autostart", "loud", "no-autologin", "no-emulator"),
    "fetch": ("host", "tools", "system"),
    "forget": ("no-system",),
}


# -- the machine this is running on ------------------------------------------


def run(command, seconds=COMMAND_SECONDS):
    """Runs one command and answers what it said.

    @param command - The argument list. Never a string and never a shell, so
      there is nothing here that could be talked into running something else.
    @param seconds - How long to wait before giving up.
    @returns str, its output with the whitespace taken off.
    @raises Refused where it failed, timed out or is not installed at all.

    apt is told there is nobody to ask, because a package putting a question up
    would wait for an answer from a console this has none of.
    """
    environment = dict(os.environ, DEBIAN_FRONTEND="noninteractive")
    try:
        answer = subprocess.run(command, capture_output=True, text=True,
                                timeout=seconds, env=environment, check=False)
    except subprocess.TimeoutExpired as error:
        raise Refused("setup.took-too-long", command=command[0],
                      seconds=seconds) from error
    except OSError as error:
        raise Refused("setup.no-such-command", command=command[0]) from error

    if answer.returncode != 0:
        raise Refused("setup.command-failed", command=command[0],
                      code=answer.returncode)
    return answer.stdout.strip()


def installed(package):
    """@returns bool - Whether dpkg has that package in place."""
    try:
        answer = subprocess.run(
            ["dpkg-query", "-W", "-f=${Status}", package],
            capture_output=True, text=True, check=False)
    except OSError:
        return False
    return "ok installed" in answer.stdout


class Owner:
    """Whoever owns the emulator, which is the user the tool runs as.

    Read from the tool's own unit, because that is where it is decided. Nothing
    here is written by this program under root's name: a file in that person's
    home belongs to them.
    """

    def __init__(self, name):
        entry = pwd.getpwnam(name)
        self.name = name
        self.uid = entry.pw_uid
        self.gid = entry.pw_gid
        self.group = grp.getgrgid(entry.pw_gid).gr_name
        self.home = pathlib.Path(entry.pw_dir)

    @classmethod
    def from_unit(cls, unit=SERVICE_UNIT):
        """@returns Owner. @raises Refused where the unit cannot be read."""
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
                 into=OUR_DIRECTORY):
        self.job = job
        self.steps = steps
        self.owner = owner
        self.system = system
        self.machine = machine
        self.settings = settings
        self.into = into
        self.done = 0
        self.step = None
        self.part = None
        self.failed = None
        self.undone = []
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
        """
        self._how.append((self.step, how))

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

    def through(self, done, of):
        """How far through something long, such as a download or an unpack.

        @param done - Bytes so far.
        @param of - Bytes in total, or 0 where nobody knows.

        Rate limited, because a chunk of a quarter of a megabyte arrives many
        times a second and the progress file would be rewritten for each. The
        first one of a step is written whatever the clock says, so that a
        download shows as having started rather than as a step with nothing
        happening in it.
        """
        beginning = self.part is None
        self.part = {"done": done, "of": of}
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
    run(["apt-get", "install", "-y", "-qq", *missing])
    work.undoes(lambda: run(["apt-get", "remove", "-y", "-qq", *missing]))


def _archive(work):
    """The Window Maker Live source, pinned so that only Previous comes from it."""
    if not REPOSITORY_KEY.exists():
        REPOSITORY_KEY.parent.mkdir(parents=True, exist_ok=True)
        _fetched("%s/%s.asc" % (REPOSITORY_URL, REPOSITORY_HOST),
                 REPOSITORY_KEY, work, hosts=(REPOSITORY_HOST,))
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
    run(["apt-get", "install", "-y", "-qq", EMULATOR_PACKAGE])
    work.undoes(lambda: run(["apt-get", "remove", "-y", "-qq",
                             EMULATOR_PACKAGE]))


def _newest_emulator(work):
    """The newest Previous the archive has.

    Nothing is recorded to undo. Going back to the version that was here would
    mean holding a copy of it, and apt has no idea where the old one went.
    """
    run(["apt-get", "update", "-qq"])
    run(["apt-get", "install", "-y", "-qq", "--only-upgrade", EMULATOR_PACKAGE])


def _no_emulator(work):
    """Takes Previous and its source away.

    The four tools stay. Something else on this machine may use ImageMagick or
    7zip by now, and leaving a package behind costs a few megabytes whilst
    taking one away can cost somebody their own work.
    """
    if installed(EMULATOR_PACKAGE):
        run(["apt-get", "purge", "-y", "-qq", EMULATOR_PACKAGE])
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
                 expecting=work.system)
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
        # The layout `install.sh` leaves: the disk inside a folder named after
        # the archive, beside the ROM images and the Windows binary that came
        # with it. All of it goes, because all of it came from that one archive.
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
    """
    profile = work.owner.home / PROFILE
    text = profile.read_text(encoding="utf-8") if profile.exists() else ""
    if AUTOSTART_OPENS in text:
        return

    work.owner.write(profile, text + _autostart_block(work.owner))
    work.undoes(lambda: _without_autostart(profile))


def _autostart_block(owner):
    """@returns str - What is added to the profile, markers and all."""
    return (
        "\n%s\n"
        "# Hand the first console to Previous. XDG_VTNR carries the number of\n"
        "# the text console and is set only where one is actually behind the\n"
        "# login, so an SSH session falls through and stays the way in once the\n"
        "# screen is taken.\n"
        "#\n"
        "# The wait is how the admin tool stops and starts the emulator without\n"
        "# any privileges at all: it creates %s to hold it down and removes the\n"
        "# file to let it come back. Waiting rather than exiting keeps the\n"
        "# console from falling through to a shell prompt whilst the emulator is\n"
        "# held.\n"
        "#\n"
        "# The directory it runs in is where it writes a screen grab, and the\n"
        "# admin tool reads those and removes them.\n"
        'if [ "$XDG_VTNR" = 1 ] && [ -z "$WAYLAND_DISPLAY" ]; then\n'
        "  clear\n"
        "  while [ -f %s ]; do sleep 2; done\n"
        "  mkdir -p %s\n"
        "  cd %s\n"
        "  exec cage -- /usr/bin/previous\n"
        "fi\n"
        "%s\n" % (AUTOSTART_OPENS, HOLD, HOLD,
                  owner.home / WORK_DIRECTORY, owner.home / WORK_DIRECTORY,
                  AUTOSTART_CLOSES))


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
        lines = profile.read_text(encoding="utf-8").splitlines(keepends=True)
    except OSError:
        return
    kept = []
    inside = False
    for line in lines:
        if line.strip() == AUTOSTART_OPENS:
            inside = True
            if kept and not kept[-1].strip():
                kept.pop()
        elif line.strip() == AUTOSTART_CLOSES:
            inside = False
        elif not inside:
            kept.append(line)
    profile.write_text("".join(kept), encoding="utf-8")


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
}


# -- fetching ----------------------------------------------------------------


def _fetched(url, into, work, expecting=None, hosts=None):
    """Downloads one file, saying how far it has got.

    @param url - Where from. One of ours, never anything from a request.
    @param into - pathlib.Path to write.
    @param work - The run, which is told how far through this is.
    @param expecting - A System whose size and digest this has to match, or
      None where the file is small enough that there is nothing to check.
    @param hosts - Which hosts a redirect may lead to, as suffixes. Left out,
      only the archive the systems come from is allowed.
    @raises Refused where it could not be fetched or is not what was expected.

    Redirects are followed and checked at every hop, because archive.org answers
    a download by sending the caller to whichever node holds the item, and a
    redirect that leads anywhere else ends the fetch.
    """
    opener = urllib.request.build_opener(_OnlyOurArchive(hosts))
    size = expecting.size if expecting else 0
    digest = None
    try:
        with opener.open(url, timeout=60) as answer:
            digest = _copied(answer, into, work, size)
    except (urllib.error.URLError, OSError) as error:
        raise Refused("setup.cannot-fetch",
                      name=expecting.name if expecting else url) from error

    if expecting is None:
        return
    if into.stat().st_size != expecting.size or digest != expecting.digest:
        raise Refused("setup.not-what-was-expected", name=expecting.name)


def _copied(answer, into, work, size):
    """Writes what a fetch is answering with, and answers with its digest."""
    running = hashlib.sha1()
    done = 0
    with open(into, "wb") as file:
        while True:
            chunk = answer.read(CHUNK_BYTES)
            if not chunk:
                break
            file.write(chunk)
            running.update(chunk)
            done += len(chunk)
            if size:
                work.through(done, size)
    return running.hexdigest()


class _OnlyOurArchive(urllib.request.HTTPRedirectHandler):
    """Refuses a redirect that leads off the archive.

    @param hosts - Host suffixes a redirect may lead to. None means the archive
      the systems come from, which `systems.from_our_archive` decides.

    The destination is checked again at every hop rather than once at the
    start, because whoever answers the first request chooses where the second
    one goes.
    """

    def __init__(self, hosts=None):
        self.hosts = hosts

    def redirect_request(self, request, fp, code, message, headers, newurl):
        if not self._allows(newurl):
            raise urllib.error.HTTPError(
                newurl, code, "redirected off the archive", headers, fp)
        return super().redirect_request(request, fp, code, message, headers,
                                        newurl)

    def _allows(self, url):
        if self.hosts is None:
            return systems.from_our_archive(url)
        host = urllib.parse.urlparse(url).hostname or ""
        return (urllib.parse.urlparse(url).scheme == "https"
                and any(host == name or host.endswith("." + name)
                        for name in self.hosts))


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
                     systems.UNPACKED_BYTES)
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
    @returns (job, steps, system, machine)
    @raises Refused where any of the three names is not one this knows.

    Every value is a key of a table. Nothing in a request is a path, a URL, a
    command or a number, so there is nothing here to get right beyond looking a
    name up and refusing the rest.
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

    return job, tuple(JOBS[job]), system, machine


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
        job, steps, system, machine = asked_for(request)
    except Refused as refusal:
        Work("?", (), None, None, None).ends(False, dict(refusal.told))
        return 1

    try:
        owner = Owner.from_unit()
    except Refused as refusal:
        Work(job, steps, None, system, machine).ends(False, dict(refusal.told))
        return 1

    work = Work(job, steps, owner, system, machine,
                Settings.load(home=owner.home))
    return 0 if carry_out(work) else 1


if __name__ == "__main__":
    sys.exit(main())
