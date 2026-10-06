"""What every core is doing, cheap enough to ask once a second.

`pi.py` answers the question a person asks when they open a window to check on
the board, and it may fork for it: `vcgencmd` twice and `ps` once. That is the
right shape at one answer every five seconds and the wrong one for a monitor
that draws a live picture. Measured on a Raspberry Pi 5 on 2026-09-28: reading
`/proc/stat` and `/proc/loadavg` together takes 0.073 ms, one `vcgencmd` fork
takes 1.5 ms, and a whole answer to `/api/pi` takes 9.9 ms.

So nothing here forks. Everything is a file under `/proc`, which is the kernel
answering out of memory it already holds. A whole reading costs 0.42 ms on that
same Pi while the emulator runs, and 0.13 ms while it does not, which at one
a second is four hundredths of one per cent of one core.

**Every figure here is a difference between two moments.** The counters in
`/proc/stat` are totals since the board started, and a total says nothing about
now: a machine that was busy for an hour this morning carries that hour for as
long as it stays up. So this keeps the last sample and reports what has changed
since, which is what a load monitor has always done.

That has two consequences worth knowing. The first answer after the service
starts has nothing to compare against and says `None` rather than a figure it
cannot have. And two browsers asking at once shorten each other's window, since
each call takes the sample the one before it left; the percentages stay right,
because they are measured against the real time between the two samples rather
than against an interval anybody assumed.
"""

import os
import pathlib
import time

from . import pi, screen

#: Where the kernel reports itself. Named rather than written into each
#: function, so a test points them at its own directory.
STAT = pathlib.Path("/proc/stat")
LOADAVG = pathlib.Path("/proc/loadavg")
PROCESSES = pathlib.Path("/proc")

#: Which fields of a `cpu` line in `/proc/stat` are time the core spent doing
#: nothing, counted from the first field after the name: idle and iowait, in
#: the order the kernel writes them.
IDLE_FIELDS = (3, 4)

#: How many of those counters tick per second. The kernel reports its times in
#: these rather than in seconds, and the value is the same on every Raspberry
#: Pi OS build, which is exactly why it is asked for rather than written down.
TICKS_PER_SECOND = os.sysconf("SC_CLK_TCK")

#: Which fields of `/proc/<pid>/stat` are the time the process itself spent on
#: a core, and when it started, as indices after the process name. The name is
#: in brackets and may hold spaces, so everything is counted from the closing
#: bracket rather than from the beginning of the line.
UTIME_FIELD = 11
STIME_FIELD = 12
STARTTIME_FIELD = 19

#: The last sample, as (when, cores, emulator ticks), or None before the first
#: one. `when` is the monotonic clock, because the wall clock can step.
_LAST = None

#: Which process is the emulator, once it has been found. Checked against its
#: own name on every reading, so a stale number answers nothing: the scan below
#: walks a few hundred directories, and doing that once a second would cost
#: more than everything else here put together.
_PID = None

#: How often to look for the emulator while it is not running. Finding it
#: costs a read per process, which is 5.6 ms on a Pi 5 against the 0.07 ms
#: everything else here comes to, and a machine that is switched off stays
#: switched off for minutes rather than for a second. When it is running there
#: is nothing to look for: the number is already known and checking it is one
#: read.
LOOK_EVERY_SECONDS = 5

#: When that last happened, or None.
_LOOKED_AT = None


def readings():
    """Everything a monitor draws, in one answer.

    @returns dict with `cores`, `load`, `memory` and `emulator`. Anything that
      could not be read is None, and the window draws that as empty rather
      than as zero.
    """
    global _LAST

    now = time.monotonic()
    cores = _cpu_times()
    ticks = _emulator_ticks()
    before = _LAST
    _LAST = (now, cores, ticks)

    seconds = now - before[0] if before else 0
    return {
        "cores": _busy(cores, before[1] if before else None),
        "load": _load(),
        "memory": pi.memory(),
        "emulator": _emulator(ticks, before[2] if before else None, seconds),
    }


def forget():
    """Throws the last sample and the process number away, so a test starts
    from the state a service that has just come up is in."""
    global _LAST, _PID, _LOOKED_AT
    _LAST = None
    _PID = None
    _LOOKED_AT = None


def _cpu_times():
    """How long every core has been busy and how long it has existed.

    @returns dict of the kernel's own name for each core, such as `cpu0`, to
      (busy ticks, total ticks). Empty where `/proc/stat` cannot be read.

    The summary line the kernel writes first is left out. It is the sum of the
    others, and a monitor that draws one bar per core has no use for it.
    """
    found = {}
    try:
        lines = STAT.read_text().splitlines()
    except OSError:
        return found

    for line in lines:
        fields = line.split()
        name = fields[0] if fields else ""
        if not name.startswith("cpu") or name == "cpu":
            continue
        try:
            times = [int(field) for field in fields[1:]]
        except ValueError:
            continue
        total = sum(times)
        idle = sum(times[field] for field in IDLE_FIELDS if field < len(times))
        found[name] = (total - idle, total)
    return found


def _busy(now, before):
    """What each core has been doing since the last reading.

    @param now - What `_cpu_times` just read.
    @param before - What it read last time, or None.
    @returns list of percentages in the kernel's own order, or None where
      there is nothing to compare against.

    A core that appears between two readings has no figure of its own yet and
    is reported as 0 rather than left out, so the window keeps one bar per core
    rather than changing shape underneath somebody.
    """
    if not now:
        return None
    if not before:
        return None

    percentages = []
    for name in sorted(now):
        busy, total = now[name]
        was_busy, was_total = before.get(name, (busy, total))
        spent = total - was_total
        if spent <= 0:
            percentages.append(0.0)
            continue
        percentages.append(round((busy - was_busy) * 100 / spent, 1))
    return percentages


def _load():
    """The three load averages, and what they should be read against.

    @returns dict with `one`, `five`, `fifteen` and `cores`, or None.

    The core count travels with them because the figures mean nothing without
    it: 4.0 is a machine working flat out on four cores and a machine four
    times oversubscribed on one.
    """
    try:
        fields = LOADAVG.read_text().split()
        one, five, fifteen = (float(field) for field in fields[:3])
    except (OSError, ValueError):
        return None
    return {"one": one, "five": five, "fifteen": fifteen,
            "cores": os.cpu_count()}


def _emulator(ticks, before, seconds):
    """What the emulator has cost since the last reading.

    @param ticks - (its own ticks, its start time), or None where it is not
      running.
    @param before - The same from the reading before, or None.
    @param seconds - How long ago that reading was.
    @returns dict with `cpu_percent`, `memory_mb` and `uptime_seconds`, or None
      where the emulator is not running.

    The percentage is of one core, so a NeXTdimension running its second thread
    reads above 100 and nothing is wrong. `ps` would answer this too, and its
    answer is the average since the process started, which on a machine that
    has been up for days is a figure about last Tuesday.
    """
    if ticks is None or _PID is None:
        return None

    spent = None
    if before is not None and seconds > 0:
        spent = round((ticks[0] - before[0]) * 100 / (TICKS_PER_SECOND * seconds), 1)

    return {
        "cpu_percent": spent,
        "memory_mb": _emulator_memory(),
        "uptime_seconds": _emulator_uptime(ticks[1]),
    }


def _emulator_ticks():
    """@returns (ticks on a core, start time in ticks), or None.

    Both come out of the one line `/proc/<pid>/stat` holds, because reading it
    twice would be two answers about two moments.
    """
    pid = _emulator_pid()
    if pid is None:
        return None
    try:
        line = (PROCESSES / str(pid) / "stat").read_text()
        after = line[line.rindex(")") + 1:].split()
        return (int(after[UTIME_FIELD]) + int(after[STIME_FIELD]),
                int(after[STARTTIME_FIELD]))
    except (OSError, ValueError, IndexError):
        return None


def _emulator_memory():
    """@returns How much the emulator is holding, in megabytes, or None.

    The resident figure, which is the second field of `/proc/<pid>/statm` and
    is counted in pages.
    """
    pid = _emulator_pid()
    if pid is None:
        return None
    try:
        pages = int((PROCESSES / str(pid) / "statm").read_text().split()[1])
    except (OSError, ValueError, IndexError):
        return None
    return pages * os.sysconf("SC_PAGE_SIZE") // (1024 * 1024)


def _emulator_uptime(started_at):
    """@returns How long the emulator has been running, in seconds, or None.

    Its start is written down as how far into this boot it happened, so the
    board's own uptime is the other half of the sum.
    """
    try:
        booted_for = float((PROCESSES / "uptime").read_text().split()[0])
    except (OSError, ValueError, IndexError):
        return None
    return max(0, int(booted_for - started_at / TICKS_PER_SECOND))


def _emulator_pid():
    """Which process is the emulator.

    @returns int, or None where it is not running, or where the last look for
      it was too recent to be worth repeating.

    Kept between readings and checked against its own name each time. A process
    that has gone takes its number with it, and a number that now belongs to
    something else fails that check, which is what makes keeping it safe.

    Looking for it afresh is the expensive part, because it means a read per
    process on the machine. So while there is nothing to find, that happens
    every few seconds rather than every reading: an emulator that is not
    running is not about to be missed by a monitor that notices it five seconds
    later.
    """
    global _PID, _LOOKED_AT

    if _PID is not None and _named(_PID) == screen.EMULATOR:
        return _PID

    _PID = None
    now = time.monotonic()
    if _LOOKED_AT is not None and now - _LOOKED_AT < LOOK_EVERY_SECONDS:
        return None
    _LOOKED_AT = now

    try:
        entries = sorted(PROCESSES.iterdir())
    except OSError:
        return None

    for entry in entries:
        if not entry.name.isdigit():
            continue
        if _named(entry.name) == screen.EMULATOR:
            _PID = int(entry.name)
            return _PID
    return None


def _named(pid):
    """@returns What a process calls itself, or None where it has gone."""
    try:
        return (PROCESSES / str(pid) / "comm").read_text().strip()
    except OSError:
        return None
