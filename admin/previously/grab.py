"""A picture of the emulated screen.

Previous can write its own framebuffer to a file, and that is the picture worth
having: it is the machine's own 1120 by 832, pixel for pixel, rather than the
emulator's window scaled to whatever screen the Pi is plugged into. The
emulator offers it as a keyboard shortcut and writes the file into whatever
directory it was started in.

So taking a picture is three steps: press the keys, wait for a file that was
not there before and is finished, and read it. It is then kept in the folder
Previously shows as Documents/Pictures, and the emulator's own copy is removed,
because a picture already sent to a browser is one nobody will ask the disk for
again, and a directory that fills up with them is this service's doing. Where
that directory cannot be written in, the grab is not asked for at all, since
taking a picture must not be a way of leaving litter in somebody's home.

Failing that, ImageMagick photographs the emulator's window. That is the
smaller picture and the one that is scaled, and it is here so that a screen can
still be seen when the better way is out of reach.
"""

import datetime
import os
import pathlib
import shutil
import subprocess
import time

from . import screen

#: What Previous maps the grab to, from its own [ShortcutsWithModifiers] where
#: kScreenshot is G. The modifier is the emulator's own rather than the
#: guest's, so the key never reaches NeXTSTEP.
GRAB_KEYS = "ctrl+alt+g"

#: What it calls what it writes, which is a stem, a count and the extension.
GRAB_GLOB = "next_screen_*.png"

#: How long to wait for the file to appear, and how often to look. The
#: emulator writes it as soon as the key lands, so this is the difference
#: between slow and never.
GRAB_TIMEOUT_SECONDS = 5
LOOK_EVERY_SECONDS = 0.1

#: How long to give ImageMagick. It either photographs the window at once or
#: cannot reach it at all.
IMPORT_TIMEOUT_SECONDS = 10

#: What a picture is, for whoever sends it on.
PNG = "image/png"

#: How a PNG begins and how it ends, from the format's own specification. The
#: end is what says the emulator has finished writing rather than started.
PNG_HEAD = b"\x89PNG\r\n\x1a\n"
PNG_TAIL = b"\x00\x00\x00\x00IEND\xaeB`\x82"


def take():
    """A picture of the emulated screen.

    @returns bytes of a PNG, or None where no picture could be taken.

    The emulator's own grab first, because it is the machine's own resolution,
    and ImageMagick against the window second.
    """
    return grabbed() or photographed()


def keep(picture, where):
    """Writes a picture into the folder pictures are kept in.

    @param picture - The bytes of a PNG.
    @param where - pathlib.Path of that folder, which is created where it is
      not there.
    @returns pathlib.Path of what was written, or None where it could not be.

    As a PNG, because these are looked at in the admin and a browser reads
    PNG. It is also the right format for what is in them: a screen is sharp
    edges and lettering, which anything lossy smears.

    Named for the moment it was taken, because that is the one thing that
    tells two pictures of the same screen apart, and written in a form that
    sorts the way it reads. The seconds are separated with full stops rather
    than colons, which a filesystem takes and a colon is not worth arguing
    with.
    """
    try:
        where.mkdir(parents=True, exist_ok=True)
        path = where / _a_name_for_now()
        path.write_bytes(picture)
    except OSError:
        return None
    return path


def _a_name_for_now():
    """@returns str, what to call a picture taken at this moment."""
    now = datetime.datetime.now().strftime("%Y-%m-%d %H.%M.%S")
    return "Screen %s.png" % now


def working_directory():
    """Where the emulator writes what it is asked to write.

    @returns pathlib.Path, or None where the emulator is not running.

    Read from the running process rather than assumed, because it is whatever
    directory the console started it in and this service does not start it.
    """
    pid = _emulator_pid()
    if pid is None:
        return None
    try:
        return pathlib.Path(os.readlink("/proc/%d/cwd" % pid))
    except OSError:
        return None


def grabbed():
    """Asks the emulator for its framebuffer and reads what it wrote.

    @returns bytes of a PNG, or None.

    Only where the file can be taken away again afterwards. The emulator
    writes into whatever directory it was started in, and a picture already
    sent to a browser that stays on the disk is one this service left there;
    do that on every press and the directory fills up. Where it cannot be
    removed the window is photographed instead, which leaves nothing behind
    and is what a machine whose emulator was started somewhere unexpected
    falls back to.

    What is watched for is a file that was not there a moment ago, because the
    emulator counts its grabs up rather than overwriting. The count is taken
    before the keys are sent, since the emulator writes the moment they land
    and a count taken afterwards would already hold what it is waiting for.
    """
    where = working_directory()
    if where is None or not os.access(where, os.W_OK):
        return None

    before = set(where.glob(GRAB_GLOB))
    if not screen.press(GRAB_KEYS):
        return None

    written = _waits_for_a_whole_picture(where, before)
    if written is None:
        return None

    try:
        picture = written.read_bytes()
    except OSError:
        picture = None
    _remove(written)
    return picture or None


def photographed():
    """Photographs the emulator's window with ImageMagick.

    @returns bytes of a PNG, or None.

    The window rather than the root, because Xwayland under cage has no root
    window worth capturing. Trimmed, because the window is whatever size the
    Pi's own screen is and Previous fills the difference around the machine's
    screen with black: untrimmed, a picture of a 1120 by 832 machine arrives
    as 1024 by 600 with bars down two sides of it.

    What is left is still the emulator's scaling of the machine's screen
    rather than the machine's own pixels. That is what this is: the picture
    for when the grab cannot be reached.
    """
    window = screen.window()
    if window is None or shutil.which("import") is None:
        return None
    try:
        result = subprocess.run(
            ["import", "-window", window, "-trim", "+repage", "png:-"],
            capture_output=True, timeout=IMPORT_TIMEOUT_SECONDS, check=False,
            env=dict(os.environ, DISPLAY=screen.display()),
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result.stdout or None


def _waits_for_a_whole_picture(where, before):
    """The file the emulator has just finished writing.

    @param where - The directory it writes into.
    @param before - What was already there.
    @returns pathlib.Path, or None where nothing whole arrived in time.

    Whole rather than merely present, because the file exists from the first
    byte and the emulator is still filling it. Read at that moment it comes
    back as whatever had been flushed, which is a picture a browser draws
    half of: measured on the machine, 32768 bytes of a 62287 byte grab.

    A PNG ends in its IEND chunk and nothing follows it, so that is the
    question being asked, and it is exact rather than a guess about timing.
    """
    until = time.monotonic() + GRAB_TIMEOUT_SECONDS
    while time.monotonic() < until:
        new = set(where.glob(GRAB_GLOB)) - before
        # Whichever is newest, because more than one arriving at once would
        # mean somebody else was grabbing too.
        newest = max(new, key=lambda path: path.stat().st_mtime, default=None)
        if newest is not None and _is_whole(newest):
            return newest
        time.sleep(LOOK_EVERY_SECONDS)
    return None


def _is_whole(path):
    """@returns bool, whether that file is a PNG that has been finished."""
    try:
        with path.open("rb") as file:
            if file.read(len(PNG_HEAD)) != PNG_HEAD:
                return False
            file.seek(-len(PNG_TAIL), os.SEEK_END)
            return file.read(len(PNG_TAIL)) == PNG_TAIL
    except OSError:
        return False


def _remove(path):
    """Takes a grab away once it has been read."""
    try:
        path.unlink()
    except OSError:
        pass


def _emulator_pid():
    """@returns the emulator's process id, or None."""
    try:
        result = subprocess.run(
            ["pgrep", "-x", screen.EMULATOR], capture_output=True, text=True,
            timeout=screen.TIMEOUT_SECONDS, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    first = result.stdout.split()
    return int(first[0]) if first and first[0].isdigit() else None
