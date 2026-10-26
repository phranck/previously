"""A picture of the emulated screen.

Previous can write its own framebuffer to a file, and that is the picture worth
having: it is the machine's own 1120 by 832, pixel for pixel, rather than the
emulator's window scaled to whatever screen the Pi is plugged into. The
emulator offers it as a keyboard shortcut and writes the file into its
printer's directory, which its configuration names and `setup.py` sets to the
directory the emulator runs in.

So taking a picture is three steps: press the keys, wait for a file that was
not there before and is finished, and read it. It is then kept in the folder
Previously shows as Documents/Pictures, and the emulator's own copy is removed,
because a picture already sent to a browser is one nobody will ask the disk for
again, and a directory that fills up with them is this service's doing. Where
that directory cannot be written in, the grab is not asked for at all, since
taking a picture must not be a way of leaving litter in somebody's home.
"""

import datetime
import os
import pathlib
import time

from . import config, emulator, png

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

#: What a picture is, for whoever sends it on.
PNG = "image/png"

#: How a PNG begins and how it ends, from the format's own specification. The
#: end is what says the emulator has finished writing rather than started.
PNG_HEAD = b"\x89PNG\r\n\x1a\n"
PNG_TAIL = b"\x00\x00\x00\x00IEND\xaeB`\x82"


def looks_alive(previous_config):
    """Whether the emulated screen is showing anything at all.

    @param previous_config - pathlib.Path to the emulator's configuration, or
      None, where nothing can be grabbed.
    @returns True where something is drawn, False where the screen is one
      color, and None where it could not be read.

    Previous says nothing about the machine inside it. A configuration it
    cannot run can leave the emulator running and its screen one color, so the
    process table says everything is fine while nothing has booted. The screen
    is the only place that difference shows, and a screen that has booted is
    never one color: even before NeXTSTEP loads, the boot ROM has put its
    panel up.

    None rather than False when there is no reading, and the difference
    matters: a grab that fails must not make every machine look broken. Only a
    screen that was read and found to be one color is False.
    """
    if previous_config is None:
        return None
    picture = grabbed(previous_config)
    if picture is None:
        return None
    try:
        return not png.one_color(picture)
    except png.Unreadable:
        return None


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
    sorts the way it reads. The seconds are separated with periods rather
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


def grabbed(previous_config):
    """Asks the emulator for its framebuffer and reads what it wrote.

    @param previous_config - pathlib.Path to the emulator's configuration.
    @returns bytes of a PNG, or None.

    Only where the file can be taken away again afterwards. A picture already
    sent to a browser that stays on the disk is one this service left there;
    do that on every press and the directory fills up. Where it cannot be
    removed no grab is asked for, so nothing is left behind. That is what a
    configuration naming no directory comes to, because Previous then writes
    into the home and this service may not write there.

    What is watched for is a file that was not there a moment ago, because the
    emulator counts its grabs up rather than overwriting. The count is taken
    before the keys are sent, since the emulator writes the moment they land
    and a count taken afterwards would already hold what it is waiting for.

    A file that was there already and is older than a grab waits goes first.
    It is what a grab that gave up got afterwards, and to every later grab it
    is already there, so nothing else would ever remove it. The count of what
    is there is taken after that sweep, because the emulator names a grab by
    the lowest number not taken: the name just swept is the name the next
    grab gets, and taken before the sweep it would read as already there.
    """
    if emulator.pid() is None:
        return None
    where = config.output_directory(previous_config, pathlib.Path.home())
    if not os.access(where, os.W_OK):
        return None

    for left in _left_behind(where.glob(GRAB_GLOB)):
        _remove(left)
    before = set(where.glob(GRAB_GLOB))
    if not emulator.press(GRAB_KEYS):
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


def _left_behind(found):
    """The grabs among these that no grab is waiting for any more.

    @param found - The grab files in the directory, before the keys are sent.
    @returns list of pathlib.Path, the ones older than GRAB_TIMEOUT_SECONDS.

    A grab gives up after that long, and a file the emulator writes after it
    gave up is nobody's: the grab that asked for it has answered with nothing,
    and every grab after it counts the file as already there. Two such grabs
    stayed in the emulator's directory on a Pi 5 on 23.10.2026. One younger
    than that may still be what another grab in flight is waiting for, since a
    status poll and a press of Grab can run at once, so it stays.
    """
    oldest = time.time() - GRAB_TIMEOUT_SECONDS
    left = []
    for path in found:
        try:
            if path.stat().st_mtime < oldest:
                left.append(path)
        except OSError:
            continue
    return left


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
