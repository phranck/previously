"""The wire that reaches the emulator.

Everything that reaches the emulator goes through the same wire, so it is here
rather than in each caller: which display it is on, which window is its own,
and how a key gets to it. Whether the screen shows anything is answered in
`grab.py`, from Previous's own picture of it.
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

#: And what it calls its process. Whether it is running is the only honest
#: signal that the guest has finished shutting down, because the unit stays
#: active either way: it holds a login shell, not the emulator.
EMULATOR = "previous"

#: Anything with a name at all, which under cage is the emulator and nothing
#: else. Why that is needed is at window below.
ANY_WINDOW = "."

#: How long to wait for either command. Both answer at once or not at all.
TIMEOUT_SECONDS = 5


def press(keys):
    """Sends a key or a shortcut to the emulator.

    @param keys - What xdotool calls them, such as "F10" or "ctrl+alt+g".
    @returns bool, whether it was sent.

    Through the X server. Previous runs as an X client under the kiosk's
    Xwayland, so keys reach it through XTEST and not through Wayland. That was
    measured rather than assumed, and measured in both directions: a Wayland
    virtual keyboard binds its protocol against the compositor and reports
    success, and the emulator never sees the key. If this ever stops working,
    the first thing to check is whether Previous has become a Wayland client,
    because then the whole route changes rather than the key names.

    It goes to whatever the kiosk has in front, which under cage is the
    emulator and nothing else.
    """
    if shutil.which("xdotool") is None:
        return False
    environment = _environment()
    if environment is None:
        return False
    try:
        return subprocess.run(
            ["xdotool", "key", "--clearmodifiers", keys],
            capture_output=True, text=True, timeout=TIMEOUT_SECONDS,
            check=False, env=environment).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def window():
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
    environment = _environment()
    if environment is None:
        return ""
    try:
        result = subprocess.run(
            command, capture_output=True, text=True,
            timeout=TIMEOUT_SECONDS, check=False, env=environment,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return result.stdout.strip()


def _environment():
    """@returns the environment a command needs in order to reach the kiosk's
      X server, or None where there is none to reach."""
    where = display()
    return dict(os.environ, DISPLAY=where) if where else None


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
