"""What the emulated screen is showing.

Previous says nothing about the machine inside it. A configuration it cannot
run leaves the emulator running and the screen blank, so the process table says
everything is fine whilst nothing has booted. The screen is the only place that
difference shows.

One reading is enough, because the question is not what is on the screen but
whether anything is. A screen that has booted is never one flat colour: even
before NeXTSTEP loads, the boot ROM has put its panel up.
"""

import os
import shutil
import subprocess

#: Where an X server puts its socket. The kiosk's Xwayland is the one this
#: service talks to, and its display number comes from the name of the file
#: it leaves here.
X11_SOCKETS = "/tmp/.X11-unix"

#: What Previous calls its window.
WINDOW = "Previous"

#: Anything with a name at all, which under cage is the emulator and nothing
#: else. Why that is needed is at _window below.
ANY_WINDOW = "."

#: How long to wait for either command. Both answer at once or not at all.
TIMEOUT_SECONDS = 5

#: Below this spread the screen is one colour and nothing has been drawn on it.
#: Measured on the machine on 14 September 2026: a machine that never booted
#: reports 0 with one colour, and a running NeXTSTEP desktop 15045 with 256.
BLANK = 1.0


def looks_alive():
    """Whether the emulated screen is showing anything at all.

    @returns True where something is drawn, False where the screen is one flat
      colour, and None where it could not be read.

    None rather than False when the reading fails, and the difference matters:
    a missing tool or an X server that is not there yet must not make every
    machine look broken. Only a screen that was actually read and found blank
    is False.
    """
    spread = _spread()
    if spread is None:
        return None
    return spread > BLANK


def _spread():
    """@returns The screen's standard deviation, or None where it cannot be
      read. A flat surface is zero however bright it is."""
    window = _window()
    if window is None or shutil.which("import") is None:
        return None

    # Trimmed first, because the window is wider than the machine's screen and
    # Previous fills the difference with black. A blank white screen between
    # two black bars is two colours far apart, which reads as a busy screen
    # until the bars are cut away. Measured on the machine: the whole window
    # reported 26781 and the same screen trimmed reported 0.
    answer = _ask(["import", "-window", window, "-trim",
                   "-format", "%[standard-deviation]", "info:"])
    try:
        return float(answer.split()[0])
    except (ValueError, IndexError):
        return None


def _window():
    """The emulator's window on the kiosk's display.

    @returns Its id as a string, or None where there is none.

    Asked for by name first and by nothing second. Under cage's Xwayland the
    window does not carry its name where `xdotool search --name` looks for it,
    even though `getwindowname` answers "Previous 4.4", so the name finds
    nothing there. What the fallback takes is the only window on that display,
    and under cage there is only ever one.
    """
    if shutil.which("xdotool") is None:
        return None
    for pattern in (WINDOW, ANY_WINDOW):
        answer = _ask(["xdotool", "search", "--name", pattern])
        found = [line.strip() for line in answer.splitlines() if line.strip().isdigit()]
        if found:
            return found[0]
    return None


def _ask(command):
    """Runs a command against the kiosk's X server.

    @param command - The argument list.
    @returns Its stripped output, or an empty string on any failure. Nothing
      here is worth an exception: a screen that cannot be read is a reading
      this service does not have.
    """
    where = display()
    if where is None:
        return ""
    try:
        result = subprocess.run(
            command, capture_output=True, text=True,
            timeout=TIMEOUT_SECONDS, check=False,
            env=dict(os.environ, DISPLAY=where),
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return result.stdout.strip()


def display():
    """Which X display the kiosk is on.

    @returns str such as ":0", or None where no X server is listening.

    Found from the socket rather than taken from the environment, because this
    service has no session of its own and the number is Xwayland's to choose.
    """
    try:
        sockets = sorted(
            name for name in os.listdir(X11_SOCKETS) if name.startswith("X")
        )
    except OSError:
        return None
    return ":" + sockets[0][1:] if sockets else None
