"""What the Raspberry Pi underneath is doing.

A machine that boots straight into an emulator has nobody watching it.
Everything that goes wrong looks the same from the front, which is a screen
that does not change, so the difference between a stopped emulator, a sound
device that lost its stream and a board throttling itself is invisible unless
something says so.

Every reading here comes from a file or from vcgencmd, and every one of them
answers with None rather than an exception when it cannot be had. A window that
shows four readings and a gap is more use than one that shows an error.
"""

import pathlib
import re
import shutil
import subprocess

from . import kiosk

#: How long to wait for vcgencmd. It answers in milliseconds, so anything
#: slower than this has gone wrong rather than got busy.
TIMEOUT_SECONDS = 5

#: What the bits of vcgencmd get_throttled mean. The low four are now, the high
#: four are since the machine last started, and they stay set once they have
#: been. From Raspberry Pi's own documentation.
#:
#: Names rather than words, because the browser shows these in whichever of its
#: five languages is in force and a word written here could only ever be in
#: one. `lang/en.js` and the rest carry them as `throttling.<name>`.
THROTTLING_NOW = {
    0: "under-voltage",
    1: "frequency-capped",
    2: "throttled",
    3: "temperature-limit",
}
THROTTLING_SINCE_BOOT = {
    16: "under-voltage",
    17: "frequency-capped",
    18: "throttled",
    19: "temperature-limit",
}

#: Where the kernel reports what each sound card's playback stream is doing.
#: An emulator that opened a device once and never asks again leaves this at
#: "closed" whilst its own configuration still names the card, which is the one
#: failure that looks like nothing at all.
SOUND_CARDS = pathlib.Path("/proc/asound")


def readings():
    """Everything this window shows, in one answer.

    @returns dict. Any reading that could not be had is None, and the page
      leaves that line empty rather than saying something untrue.
    """
    return {
        "model": _model(),
        "uptime_seconds": _uptime_seconds(),
        "temperature_c": _temperature(),
        "throttling": _throttling(),
        "emulator": _emulator(),
        "sound": _sound(),
        "disk": _disk(),
        "memory": _memory(),
    }


def _model():
    """@returns The board's own name, such as "Raspberry Pi 5 Model B Rev 1.1"."""
    try:
        raw = pathlib.Path("/proc/device-tree/model").read_bytes()
    except OSError:
        return None
    # The device tree writes its strings with a trailing null.
    return raw.decode("ascii", "replace").rstrip("\x00").strip() or None


def _uptime_seconds():
    """@returns How long the board has been up, in whole seconds, or None."""
    try:
        first = pathlib.Path("/proc/uptime").read_text().split()[0]
        return int(float(first))
    except (OSError, ValueError, IndexError):
        return None


def _temperature():
    """@returns The chip's temperature in degrees, or None.

    vcgencmd answers `temp=52.1'C`, with an apostrophe where a degree sign
    would go.
    """
    answer = _vcgencmd("measure_temp")
    found = re.search(r"temp=([\d.]+)", answer)
    return float(found.group(1)) if found else None


def _throttling():
    """What the board has had to do about power and heat.

    @returns dict with `now` and `since_boot`, each a list of plain words, and
      `raw` as the number itself. None where vcgencmd cannot be asked.

    Said in words rather than as a bitfield, because a reader should not have
    to hold a table of bits to find out that the power supply is not enough.
    The two halves are kept apart: something happening now is a problem, and
    something that happened once may have been the moment a drive was plugged
    in.
    """
    answer = _vcgencmd("get_throttled")
    found = re.search(r"throttled=0x([0-9a-fA-F]+)", answer)
    if not found:
        return None

    bits = int(found.group(1), 16)
    return {
        "raw": bits,
        "now": [word for bit, word in THROTTLING_NOW.items() if bits & (1 << bit)],
        "since_boot": [word for bit, word in THROTTLING_SINCE_BOOT.items()
                       if bits & (1 << bit)],
    }


def _emulator():
    """What the emulator process is costing.

    @returns dict, or None where it is not running.

    Two threads run when a NeXTdimension is configured, so around 150 per cent
    of one core is ordinary here and says nothing is wrong.
    """
    answer = _ask(["ps", "-o", "etimes=,pcpu=,rss=", "-C", kiosk.EMULATOR_PROCESS])
    fields = answer.split()
    if len(fields) < 3:
        return None
    try:
        return {
            "uptime_seconds": int(fields[0]),
            "cpu_percent": float(fields[1]),
            "memory_mb": int(fields[2]) // 1024,
        }
    except ValueError:
        return None


def _sound():
    """Which card is playing, and what its stream is doing.

    @returns dict with `card` and `playing`, or None where there is no card.

    The card that matters is whichever one has a stream open. Where none has,
    the first is reported so the window can say which device sound would go to.
    """
    cards = []
    try:
        directories = sorted(SOUND_CARDS.glob("card*"))
    except OSError:
        return None

    for directory in directories:
        name = _first_line(directory / "id")
        state = _first_line(directory / "pcm0p/sub0/status")
        if name is None:
            continue
        cards.append({"card": name, "playing": state == "state: RUNNING"})

    if not cards:
        return None
    return next((card for card in cards if card["playing"]), cards[0])


def _disk():
    """How much room is left where everything lives.

    @returns dict with `free_mb` and `used_percent`, or None.

    The disk image and the shared directory are both on the card, so this is
    the one number that decides whether either can grow.
    """
    try:
        usage = shutil.disk_usage("/")
    except OSError:
        return None
    return {
        "free_mb": usage.free // (1024 * 1024),
        "total_mb": usage.total // (1024 * 1024),
        "used_percent": round((usage.total - usage.free) * 100 / usage.total),
    }


def _memory():
    """@returns dict with `total_mb` and `available_mb`, or None.

    Available rather than free, because Linux lends unused memory to the page
    cache and free alone makes a healthy machine look exhausted.
    """
    wanted = {"MemTotal": None, "MemAvailable": None}
    try:
        for line in pathlib.Path("/proc/meminfo").read_text().splitlines():
            key, _, rest = line.partition(":")
            if key in wanted:
                wanted[key] = int(rest.split()[0]) // 1024
    except (OSError, ValueError, IndexError):
        return None

    if wanted["MemTotal"] is None or wanted["MemAvailable"] is None:
        return None
    return {"total_mb": wanted["MemTotal"], "available_mb": wanted["MemAvailable"]}


def _first_line(path):
    """@returns The first line of a file, stripped, or None."""
    try:
        with path.open() as handle:
            return handle.readline().strip()
    except OSError:
        return None


def _vcgencmd(*arguments):
    """@returns What vcgencmd said, or an empty string."""
    return _ask(["vcgencmd", *arguments])


def _ask(command):
    """Runs a reading command.

    @param command - The argument list.
    @returns Its stripped output, or an empty string on any failure. Nothing
      here is worth an exception: a reading that cannot be had is a blank line
      in a window.
    """
    try:
        result = subprocess.run(
            command, capture_output=True, text=True,
            timeout=TIMEOUT_SECONDS, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return result.stdout.strip()
