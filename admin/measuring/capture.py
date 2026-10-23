"""Writes down one start of the emulator, second by second, on the Pi.

`boot.py` copies this file and the `previously` package beside it onto the Pi
and starts it from a systemd user unit, which runs with the first login of the
user the emulator belongs to. On a Pi Previously set up, that login is the
console that starts the emulator, so this is there for the whole of NeXTSTEP's
boot without any privilege.

Every second it keeps three things: the emulator's screen as Previous grabs it,
the time each of the emulator's threads has spent on a core, and the same for
every process on the board. Nothing is worked out here. The Pi has no image
library, and the times mean nothing until the screen says when the boot ended,
so `boot.py` reads all of it on the Mac afterwards.

Grabbing costs the emulator a little, because Previous encodes each picture
itself. It does that once a second in every measurement, so it is the same in
each and does not change a comparison between them.

    python3 -I capture.py <directory> <seconds after the emulator started>
"""

import json
import os
import pathlib
import sys
import time

# Run with -I, which leaves the script's own directory off the path, so the
# package copied beside it is put there by hand.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from previously import activity, grab, screen  # noqa: E402
from previously.settings import Settings  # noqa: E402

#: Where the kernel reports its processes.
PROCESSES = pathlib.Path("/proc")

#: How often a reading is taken. Once a second, because a boot is a minute or
#: two and a picture each second says when it ended to within that second.
EVERY_SECONDS = 1

#: How long to wait for the emulator to appear. The console starts it right
#: after the login this unit starts with, so minutes mean it is not coming.
WAIT_FOR_EMULATOR_SECONDS = 300
LOOK_EVERY_SECONDS = 0.2

#: What the kernel counts a core's time in, per second.
TICKS_PER_SECOND = os.sysconf("SC_CLK_TCK")

#: What the record is called, and the file that says it is complete.
RECORD = "capture.json"
DONE = "done"


def main(argv):
    """Waits for the emulator, then reads it every second for as long as asked.

    @param argv - The script's name, the directory to write into, and how many
      seconds after the emulator's start to stop.
    @returns int, the exit status.
    """
    into = pathlib.Path(argv[1])
    seconds = float(argv[2])
    frames = into / "frames"
    frames.mkdir(parents=True, exist_ok=True)

    pid = _wait_for_emulator()
    if pid is None:
        _finish(into, {"error": "the emulator did not start"})
        return 1

    started_at = _started_at(pid)
    configuration = Settings.load().previous_config
    samples = []
    pictures = []
    while _since_boot() < started_at + seconds and _named(pid) == screen.EMULATOR:
        at = _since_boot()
        samples.append({"at": at, "threads": _threads(pid), "processes": _processes()})
        picture = grab.grabbed(configuration)
        if picture is not None:
            name = "%04d.png" % len(pictures)
            (frames / name).write_bytes(picture)
            pictures.append({"at": at, "file": name})
        time.sleep(max(0.0, at + EVERY_SECONDS - _since_boot()))

    _finish(into, {
        "ticks_per_second": TICKS_PER_SECOND,
        "emulator": {"pid": pid, "started_at": started_at},
        "samples": samples,
        "frames": pictures,
    })
    return 0


def _finish(into, record):
    """Writes the record and then the file that says it is whole, so `boot.py`
    never reads one that is still being written."""
    (into / RECORD).write_text(json.dumps(record))
    (into / DONE).touch()


def _wait_for_emulator():
    """@returns The emulator's process id, or None where it did not appear."""
    until = time.monotonic() + WAIT_FOR_EMULATOR_SECONDS
    while time.monotonic() < until:
        for entry in PROCESSES.iterdir():
            if entry.name.isdigit() and _named(entry.name) == screen.EMULATOR:
                return int(entry.name)
        time.sleep(LOOK_EVERY_SECONDS)
    return None


def _since_boot():
    """@returns Seconds since the kernel started, on the clock `/proc` counts
    a process's start in."""
    return time.clock_gettime(time.CLOCK_BOOTTIME)


def _started_at(pid):
    """@returns When the process started, in seconds since the kernel did."""
    fields = _fields(PROCESSES / str(pid) / "stat")
    return int(fields[activity.STARTTIME_FIELD]) / TICKS_PER_SECOND


def _threads(pid):
    """@returns dict of thread id to [name, ticks on a core] for the emulator."""
    return _ticks_under(PROCESSES / str(pid) / "task")


def _processes():
    """@returns dict of process id to [name, ticks on a core] for the board,
    without this capture. It is not part of what is measured, and it carries
    the same name as the admin service, which is."""
    found = _ticks_under(PROCESSES)
    found.pop(str(os.getpid()), None)
    return found


def _ticks_under(directory):
    """Reads every numbered entry's stat under a directory.

    @returns dict of its number to [name, ticks]. An entry that has gone
      between the listing and the reading is left out. A name is trimmed,
      because Previous calls its processor thread "[Previous] 68k " with a
      space at the end.
    """
    found = {}
    for entry in directory.iterdir():
        if not entry.name.isdigit():
            continue
        try:
            line = (entry / "stat").read_text()
        except OSError:
            continue
        name = line[line.index("(") + 1:line.rindex(")")].strip()
        fields = line[line.rindex(")") + 1:].split()
        found[entry.name] = [name, int(fields[activity.UTIME_FIELD])
                             + int(fields[activity.STIME_FIELD])]
    return found


def _fields(path):
    """@returns The fields of a stat file after the name in brackets."""
    line = path.read_text()
    return line[line.rindex(")") + 1:].split()


def _named(pid):
    """@returns What a process calls itself, or None where it has gone."""
    try:
        return (PROCESSES / str(pid) / "comm").read_text().strip()
    except OSError:
        return None


if __name__ == "__main__":
    sys.exit(main(sys.argv))
