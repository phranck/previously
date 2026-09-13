"""Everything this service asks of systemd, in one place.

It is one module because it is the whole privilege surface. Reviewing what the
tool may do to the machine means reading this file, and there is nothing else
to read.

Reading state needs no privilege: `systemctl is-active` answers any user.
Changing it does, and that is deliberately not here yet. It arrives with the
narrow sudoers rule that issue #4 settles, and when it does it belongs in this
file and nowhere else.
"""

import subprocess

#: How long to wait for systemctl before giving up. A query that hangs is worse
#: than one that fails, because the page waits with it.
TIMEOUT_SECONDS = 5


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
