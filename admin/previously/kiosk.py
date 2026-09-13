"""Everything this service does to the machine, in one place.

It is one module because it is the whole surface. Reviewing what the tool may
do to the machine means reading this file, and there is nothing else to read.

None of it needs privilege. Reading state does not, because `systemctl
is-active` answers any user. Changing it does not either, because the emulator
is started and stopped through a file in this service's own state directory
rather than through systemd. Why that is so is explained at hold_path below.
"""

import os
import shutil
import subprocess
import time

#: How long to wait for systemctl before giving up. A query that hangs is worse
#: than one that fails, because the page waits with it.
TIMEOUT_SECONDS = 5

#: The key Previous maps to the NeXT power button. Pressing it starts an
#: orderly shutdown inside the guest, exactly as the Logout panel's Power Off
#: does. Taking the emulator away instead leaves the guest's file system dirty,
#: which costs a file system check on the way back up.
POWER_KEY = "F10"

#: The emulator's process name. Whether it is running is the only honest
#: signal that the guest has finished shutting down, because the unit stays
#: active either way: it holds a login shell, not the emulator.
EMULATOR_PROCESS = "previous"

#: How long to give the guest after the power button. NeXTSTEP flushes and
#: unmounts at its own pace, and a guest still writing is the one case where
#: waiting longer is right, so this is generous on purpose.
SHUTDOWN_TIMEOUT_SECONDS = 120

#: How often to look while waiting.
POLL_SECONDS = 1


def is_running(unit):
    """Whether the kiosk unit is active.

    @param unit - The unit's name, such as `getty@tty1.service`.
    @returns bool. False where systemctl is absent, times out or errors, since
      the question being unanswerable and the answer being no look the same
      from the page and neither is worth an exception.
    """
    return _ask(["systemctl", "is-active", unit]) == "active"


def uptime_seconds(unit):
    """How long the unit has been active, or None where it is not.

    @param unit - The unit's name.
    @returns int or None
    """
    stamp = _property(unit, "ActiveEnterTimestampMonotonic")
    if not stamp or stamp == "0":
        return None
    try:
        started = int(stamp) / 1_000_000
    except ValueError:
        return None
    return max(0, int(_monotonic() - started))


def hold_path(state_directory):
    """Where the file that holds the emulator down lives.

    @param state_directory - The service's own directory, which the unit
      creates through StateDirectory= and which is the one place it may write.
    @returns pathlib.Path

    This file is the whole start and stop mechanism, and the reason the tool
    needs no privileges. ~/.profile waits on it rather than starting the
    emulator unconditionally, so creating it holds the emulator down and
    removing it lets the emulator come back.

    The obvious alternative does not work. getty@tty1 carries Restart=always
    with RestartSec=0, so when the guest powers off and the session ends,
    systemd has a fresh emulator booting within a second or two. Waiting for
    the emulator to disappear would therefore never see it gone, and a
    systemctl stop arriving afterwards would kill a guest that had just begun
    writing, which is the damage this avoids, moved one boot later.
    """
    return state_directory / "hold"


def is_held(state_directory):
    """Whether the emulator is being held down.

    @param state_directory - The service's own directory.
    @returns bool
    """
    return hold_path(state_directory).exists()


def emulator_is_running():
    """Whether the emulator process exists.

    @returns bool. False where pgrep is absent or fails, because a question
      that cannot be answered and an answer of no look the same from the page.

    Distinct from is_running, which answers about the unit. The unit is active
    whether the emulator runs or not, because what it holds is a login shell.
    """
    return _ask(["pgrep", "-x", EMULATOR_PROCESS]) != ""


def press_power():
    """Presses the emulated power button, starting an orderly shutdown.

    @returns bool, whether the key reached the compositor.

    Sent with wtype through the Wayland virtual keyboard protocol, which the
    cage compositor running the kiosk implements. The environment it needs is
    worked out rather than assumed, because the socket's name is the
    compositor's to choose.
    """
    environment = _compositor_environment()
    if environment is None:
        return False
    if shutil.which("wtype") is None:
        return False
    try:
        result = subprocess.run(
            ["wtype", "-k", POWER_KEY],
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
            check=False,
            env=environment,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def stop(state_directory, timeout=SHUTDOWN_TIMEOUT_SECONDS, sleep=time.sleep):
    """Shuts the guest down properly and keeps the emulator down afterwards.

    @param state_directory - The service's own directory.
    @param timeout - Seconds to wait for the guest before giving up.
    @param sleep - Injected so a test does not wait in real time.
    @returns (bool, str). The second is what to tell the user, whether it
      worked or not.

    The hold goes on before the key, so that the session ending finds it
    already there. Doing it the other way round leaves a gap in which the
    emulator comes straight back.
    """
    hold_path(state_directory).touch()

    if not emulator_is_running():
        return True, "the emulator was not running, and is now held down"

    if not press_power():
        hold_path(state_directory).unlink(missing_ok=True)
        return False, "the power button could not be pressed, so nothing was changed"

    if not _wait_for_shutdown(timeout, sleep):
        return False, (
            "NeXTSTEP has not finished shutting down after %d seconds. "
            "It is still held down, so nothing will start it again, and a "
            "guest that is still writing is the one case where waiting "
            "longer is right." % timeout
        )

    return True, "NeXTSTEP shut itself down and the emulator is held down"


def start(state_directory):
    """Lets the emulator come back.

    @param state_directory - The service's own directory.
    @returns (bool, str)

    Removing the file is the whole of it. The waiting profile on the console
    notices within a couple of seconds and starts the emulator itself.
    """
    if not is_held(state_directory):
        if emulator_is_running():
            return True, "the emulator is already running"
        return True, "nothing is holding the emulator down; it should come back on its own"

    hold_path(state_directory).unlink(missing_ok=True)
    return True, "the emulator is on its way back"


def restart(state_directory, timeout=SHUTDOWN_TIMEOUT_SECONDS, sleep=time.sleep):
    """Shuts the guest down properly and lets it come straight back.

    @param state_directory - The service's own directory.
    @param timeout - Seconds to wait for the guest.
    @param sleep - Injected so a test does not wait in real time.
    @returns (bool, str)

    A stop followed by a start, rather than relying on the unit restarting by
    itself, because that path is observable at every step and this one is not.
    """
    finished, reason = stop(state_directory, timeout, sleep)
    if not finished:
        return False, reason
    return start(state_directory)


def _wait_for_shutdown(timeout, sleep):
    """Waits for the emulator to go.

    @param timeout - Seconds to wait in total.
    @param sleep - How to wait between looks.
    @returns bool, False where it is still there when the time runs out.

    Counted in polls rather than against a clock, so the wait is exactly as
    long as the caller's sleep makes it and a test can pass one that returns
    at once.

    Reliable only because the hold is already in place: without it the session
    ending would bring a new emulator up and this would never see none.
    """
    for _ in range(max(1, int(timeout / POLL_SECONDS))):
        if not emulator_is_running():
            return True
        sleep(POLL_SECONDS)
    return not emulator_is_running()


def _compositor_environment():
    """The environment a Wayland client needs to reach the kiosk's compositor.

    @returns dict, or None where no compositor is listening.

    The socket is found rather than named, because which one cage opens is its
    choice. The lock file beside it is not a socket and is skipped.
    """
    runtime = os.environ.get("XDG_RUNTIME_DIR") or "/run/user/%d" % os.getuid()
    try:
        names = sorted(
            name for name in os.listdir(runtime)
            if name.startswith("wayland-") and not name.endswith(".lock")
        )
    except OSError:
        return None
    if not names:
        return None

    environment = dict(os.environ)
    environment["XDG_RUNTIME_DIR"] = runtime
    environment["WAYLAND_DISPLAY"] = names[0]
    return environment


def _property(unit, name):
    """@returns One systemd property of a unit, as a string, or None."""
    answer = _ask(["systemctl", "show", unit, "--property", name, "--value"])
    return answer or None


def _ask(command):
    """Runs a read-only systemctl query.

    @param command - The argument list.
    @returns Its stripped output, or an empty string on any failure.
    """
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return result.stdout.strip()


def _monotonic():
    """The clock systemd's monotonic timestamps are measured against.

    A separate function so a test can replace it without reaching into time.
    """
    import time
    return time.clock_gettime(time.CLOCK_BOOTTIME)
