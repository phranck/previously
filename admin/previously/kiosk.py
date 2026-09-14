"""Everything this service does to the machine, in one place.

It is one module because it is the whole surface. Reviewing what the tool may
do to the machine means reading this file, and there is nothing else to read.

Switching the emulated machine on and off needs no privilege, because that
happens through a file in this service's own runtime directory rather than
through systemd. Why that is so is explained at hold_path below.

Switching the board itself off needs none either, and that is worth saying
plainly because it looks as though it must. Only root may power a machine
down, so this tool does not: it leaves a file in its own runtime directory, and
a systemd path unit running as root does the one thing that file means. The
name of the file is the whole of the request, so there is nothing to pass and
no shell to pass it through.
"""

import os
import shutil
import subprocess
import time

from . import screen

#: How long to wait for systemctl before giving up. A query that hangs is worse
#: than one that fails, because the page waits with it.
TIMEOUT_SECONDS = 5

#: The key Previous maps to the NeXT power button, per its own manual. Taking
#: the emulator away instead leaves the guest's file system dirty, which costs
#: a file system check on the way back up.
POWER_KEY = "F10"

#: NeXTSTEP does not switch off on the power key alone. It puts up a panel
#: asking "Wollen Sie den Computer wirklich ausschalten?", whose default button
#: carries the return symbol. So the key is half of it and this is the other
#: half.
CONFIRM_KEY = "Return"

#: What quits Previous itself rather than the machine inside it, from its own
#: [ShortcutsWithModifiers]. The way out of a machine that never booted: the
#: power key reaches NeXTSTEP, and where NeXTSTEP never started there is
#: nothing for it to reach.
#:
#: It costs whatever the guest had not written, which is why it is not how a
#: machine is switched off. Previous asks before it goes, and the panel's
#: default button is the return key again.
QUIT_KEYS = "ctrl+alt+q"

#: How long to wait for the emulator to go after being told to. It has no guest
#: to shut down, so this is the time SDL takes to close a window.
QUIT_TIMEOUT_SECONDS = 15

#: How often the confirmation is pressed again whilst waiting for the guest.
#: NeXTSTEP raises its panel at its own pace, and one press at a fixed moment
#: after the power key lands on the desktop when the panel is not up yet, which
#: leaves the panel standing and the machine running.
CONFIRM_EVERY_POLLS = 4

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

#: What the board itself can be asked to do. Each name is the name of a file
#: this service creates and of the systemd path unit watching for it, so a name
#: added here without a pair of units to match is a request nothing answers.
BOARD_REQUESTS = ("reboot", "poweroff")


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


def told(name, **values):
    """One answer from this module, as a name and what fills it.

    @param name - What happened, in a form that does not change with the
      language it is read in.
    @param values - Whatever the sentence needs: a count, a machine's name, a
      number of seconds.
    @returns dict with `reason` and the rest beside it.

    A sentence written here could only ever be in one language, and this
    service has no idea which language the person reading it wants. So it says
    what happened and the browser says it in words.
    """
    return {"reason": name, **values}


def hold_path(runtime_directory):
    """Where the file that holds the emulator down lives.

    @param runtime_directory - The service's runtime directory, which the unit
      creates through RuntimeDirectory= on a tmpfs.
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

    On a tmpfs rather than on the card, so that a machine which has just
    started runs its emulator whoever switched it off before the last
    shutdown. Otherwise shutting the guest down before rebooting the board
    would bring the board back to a console waiting for a file nobody is going
    to remove.
    """
    return runtime_directory / "hold"


def is_held(runtime_directory):
    """Whether the emulator is being held down.

    @param runtime_directory - The service's runtime directory.
    @returns bool
    """
    return hold_path(runtime_directory).exists()


def emulator_is_running():
    """Whether the emulator process exists.

    @returns bool. False where pgrep is absent or fails, because a question
      that cannot be answered and an answer of no look the same from the page.

    Distinct from is_running, which answers about the unit. The unit is active
    whether the emulator runs or not, because what it holds is a login shell.
    """
    return _ask(["pgrep", "-x", EMULATOR_PROCESS]) != ""


def emulator_uptime_seconds():
    """How long the emulator has been running.

    @returns int, or None where it is not running.

    Its own age rather than the unit's. The unit holds a login shell that
    outlives any one emulator, so after a restart the unit is old and the
    emulator is new. This is also what tells a machine that came up and stayed
    up from one that is restarting over and over because it cannot run the
    configuration it was given.
    """
    answer = _ask(["ps", "-o", "etimes=", "-C", EMULATOR_PROCESS])
    ages = [int(line) for line in answer.split() if line.isdigit()]
    return min(ages) if ages else None


def press_power():
    """Presses the emulated power button.

    @returns bool, whether the key was sent.

    This raises a panel inside the guest asking whether the machine should
    really switch off. Answering it is the waiting's business, because when the
    panel appears is the guest's business and not ours.

    Sent through the X server. Previous runs as an X client under the kiosk's
    Xwayland, so keys reach it through XTEST and not through Wayland. That was
    measured rather than assumed, and measured in both directions: a Wayland
    virtual keyboard binds its protocol against the compositor and reports
    success, and the emulator never sees the key. If this ever stops working,
    the first thing to check is whether Previous has become a Wayland client,
    because then the whole route changes rather than the key names.
    """
    return _press(POWER_KEY)


def _press(key):
    """Sends one key to whatever the kiosk has in front.

    @param key - An X keysym name, such as "F10".
    @returns bool
    """
    where = screen.display()
    if where is None or shutil.which("xdotool") is None:
        return False

    environment = dict(os.environ, DISPLAY=where)
    try:
        result = subprocess.run(
            ["xdotool", "key", "--clearmodifiers", key],
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
            check=False,
            env=environment,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def stop(runtime_directory, timeout=SHUTDOWN_TIMEOUT_SECONDS, sleep=time.sleep):
    """Shuts the guest down properly and keeps the emulator down afterwards.

    @param runtime_directory - The service's runtime directory.
    @param timeout - Seconds to wait for the guest before giving up.
    @param sleep - Injected so a test does not wait in real time.
    @returns (bool, str). The second is what to tell the user, whether it
      worked or not.

    The hold goes on before the key, so that the session ending finds it
    already there. Doing it the other way round leaves a gap in which the
    emulator comes straight back.
    """
    hold_path(runtime_directory).touch()

    if not emulator_is_running():
        return True, told("emulator.was-not-running")

    # A guest that never started cannot be shut down. The power key reaches
    # NeXTSTEP, and where the screen is blank there is no NeXTSTEP to reach, so
    # pressing it only spends the whole timeout before saying so. Previous
    # itself is told instead, and the hold is already in place.
    if screen.looks_alive() is False:
        if quit_emulator(sleep=sleep):
            return True, told("emulator.ended-because-blank")
        return False, told("emulator.blank-and-will-not-end")

    if not press_power():
        hold_path(runtime_directory).unlink(missing_ok=True)
        return False, told("emulator.power-key-refused")

    if not _wait_for_shutdown(timeout, sleep):
        return False, told("guest.still-shutting-down", seconds=timeout)

    return True, told("guest.shut-itself-down")


def start(runtime_directory):
    """Lets the emulator come back.

    @param runtime_directory - The service's runtime directory.
    @returns (bool, str)

    Removing the file is the whole of it. The waiting profile on the console
    notices within a couple of seconds and starts the emulator itself.
    """
    if not is_held(runtime_directory):
        if emulator_is_running():
            return True, told("emulator.already-running")
        return True, told("emulator.nothing-holding-it")

    hold_path(runtime_directory).unlink(missing_ok=True)
    return True, told("emulator.on-its-way-back")


def quit_emulator(timeout=QUIT_TIMEOUT_SECONDS, sleep=time.sleep):
    """Ends the emulator itself, without asking the guest.

    @param timeout - How long to wait for the process to go.
    @param sleep - Injected so a test does not wait in real time.
    @returns bool, whether it went.

    For the one case the power key cannot reach: a machine that never booted.
    NeXTSTEP is not there to be asked, so the emulator is told instead, through
    Previous's own quit shortcut and the panel it raises.

    Nothing the guest had is written back, which is why this is not how a
    machine is switched off. It is how a machine that is not running is got out
    of the way, and the hold is left to the caller: this only ends the process.
    """
    was = emulator_uptime_seconds()
    if was is None:
        return True
    if not _press(QUIT_KEYS):
        return False

    sleep(1)
    _press(CONFIRM_KEY)

    # Gone means this one is gone, not that nothing is running. Nothing holds
    # the console here, so a fresh emulator is often up within a second of the
    # old one going, and asking whether one is running would see that and call
    # it a failure. A younger process is a different process.
    for _ in range(timeout):
        age = emulator_uptime_seconds()
        if age is None or age < was:
            return True
        sleep(1)
    return False


def restart(runtime_directory, timeout=SHUTDOWN_TIMEOUT_SECONDS, sleep=time.sleep):
    """Shuts the guest down properly and lets it come straight back.

    @param runtime_directory - The service's runtime directory.
    @param timeout - Seconds to wait for the guest.
    @param sleep - Injected so a test does not wait in real time.
    @returns (bool, str)

    A stop followed by a start, rather than relying on the unit restarting by
    itself, because that path is observable at every step and this one is not.
    """
    finished, reason = stop(runtime_directory, timeout, sleep)
    if not finished:
        return False, reason
    return start(runtime_directory)


def board(action, runtime_directory, timeout=SHUTDOWN_TIMEOUT_SECONDS,
          sleep=time.sleep):
    """Restarts or switches off the board, taking the guest down first.

    @param action - "reboot" or "poweroff".
    @param runtime_directory - The service's runtime directory.
    @param timeout - Seconds to wait for the guest before giving up.
    @param sleep - Injected so a test does not wait in real time.
    @returns (bool, str)

    The guest goes first and the board waits for it. A board that reboots
    underneath a running emulator does the same damage as killing the
    emulator, and to a machine that then has to come back up.

    Nothing releases the hold afterwards, and nothing needs to: it is on a
    tmpfs, so the board comes back to an empty runtime directory and the
    console starts the emulator by itself.
    """
    if action not in BOARD_REQUESTS:
        return False, told("board.no-such-action", action=action)

    stopped, reason = stop(runtime_directory, timeout, sleep)
    if not stopped:
        return False, reason

    if not _request(runtime_directory, action):
        return False, told("board.request-refused", action=action)

    return True, told("board.on-its-way", action=action)


def _request(runtime_directory, action):
    """Leaves the request where the path unit watching for it will find it.

    @param runtime_directory - The service's runtime directory.
    @param action - One of BOARD_REQUESTS.
    @returns bool, whether the file could be written.

    Writing it is the whole of what this service does. What happens next is
    previously-reboot.service or previously-poweroff.service, which systemd
    runs as root and which names one command with no arguments.
    """
    try:
        (runtime_directory / action).touch()
    except OSError:
        return False
    return True


def _wait_for_shutdown(timeout, sleep):
    """Waits for the emulator to go, answering the panel until it does.

    @param timeout - Seconds to wait in total.
    @param sleep - How to wait between looks.
    @returns bool, False where it is still there when the time runs out.

    The confirmation is pressed again every few polls rather than once at a
    fixed moment after the power key. NeXTSTEP raises its panel at its own
    pace, and a machine that has been up for hours with windows open is slower
    about it than one that has just started. A press that arrives before the
    panel lands on the desktop and does nothing, and the panel then stands
    unanswered until the time runs out.

    Pressing again costs nothing once the guest is going: there is no longer
    anything for the key to reach.

    Counted in polls rather than against a clock, so the wait is exactly as
    long as the caller's sleep makes it and a test can pass one that returns
    at once.

    Reliable only because the hold is already in place: without it the session
    ending would bring a new emulator up and this would never see none.
    """
    for attempt in range(max(1, int(timeout / POLL_SECONDS))):
        if not emulator_is_running():
            return True
        if attempt % CONFIRM_EVERY_POLLS == 0:
            _press(CONFIRM_KEY)
        sleep(POLL_SECONDS)
    return not emulator_is_running()


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
