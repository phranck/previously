"""Measures how long a Pi takes to boot into NeXTSTEP and what that costs.

The baseline every slice of #577 is held against, taken the same way each
time. `docs/measuring.md` says how to run it and what each figure means.

Everything on the Pi happens as the user the emulator belongs to, without
sudo. This copies `capture.py` and the `previously` package into that user's
home, installs a systemd user unit that runs the capture with the next login,
and restarts the board through the admin's own `kiosk.board`, which takes the
guest down first. After each start it reads `systemd-analyze` and fetches what
the capture wrote. Once every run is done it takes the unit and the files away
again, and puts the emulator's configuration back where a run changed it.

Reading the pictures needs Pillow, which is why this runs on the Mac and the
capture on the Pi only collects.

    python3 boot.py next@next5.local --into /tmp/pi5-cube
    python3 boot.py next@next5.local --into /tmp/pi5-nd --machine nextcube-turbo-dimension
    python3 boot.py --report /tmp/pi5-cube
"""

import argparse
import json
import pathlib
import re
import statistics
import subprocess
import sys
import time

from PIL import Image, ImageChops

#: Where everything this puts on the Pi lives, under the user's home, so taking
#: it away again is one directory.
REMOTE = ".cache/previously-measure"
REMOTE_CODE = REMOTE + "/code"
REMOTE_RUN = REMOTE + "/run"
REMOTE_CONFIGURATION = REMOTE + "/previous.cfg.before"

#: The user unit that starts the capture with the console's login.
UNIT = "previously-measure.service"
UNIT_PATH = ".config/systemd/user/" + UNIT

#: This file's directory, which holds `capture.py`, and the package beside it.
HERE = pathlib.Path(__file__).resolve().parent
PACKAGE = HERE.parent / "previously"

#: Python on the Pi, run against the package this copied there.
REMOTE_PYTHON = "PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=$HOME/%s python3" % REMOTE_CODE

#: How long a board may take to go down and answer SSH again, and how often to
#: ask. A Pi 4 has taken over two minutes to reach SSH.
BACK_WITHIN_SECONDS = 600
ASK_EVERY_SECONDS = 5

#: How long the capture runs after the emulator has started. A NeXTcube is at
#: its Workspace within about a minute, and what follows is the idle reading.
CAPTURE_SECONDS = 240

#: How many pixels may differ between two pictures of a screen that has stopped
#: changing. The clock in the dock turns over once a minute, which is not the
#: boot going on: 6 to 29 pixels in twelve boots on a Pi 4 and a Pi 5 on
#: 23.10.2026, with and without a NeXTdimension, where the smallest change
#: during a boot was 205.
CLOCK_PIXELS = 100

#: How long after the screen has settled the idle reading begins, so whatever
#: NeXTSTEP still does behind a finished Workspace is not counted as idle.
IDLE_AFTER_SECONDS = 10

#: How many processes the report lists beside the emulator's threads.
PROCESSES_LISTED = 8

#: Processes the report lists however little they use, because they are what
#: #571 and #572 take away, and a report after that says 0 for them.
WATCHED = ("cage", "Xwayland", "pipewire", "wireplumber", "pipewire-pulse")

#: How the kernel's workers begin their names. The rest is a number and the
#: queue a worker serves at that moment, which differ from run to run.
KERNEL_WORKER = "kworker"

#: What the report shows where a figure could not be read.
MISSING = "n/a"


# -- on the Pi -------------------------------------------------------------


def measure(target, into, runs, seconds, machine=None):
    """Starts the board `runs` times and keeps what each start showed.

    @param target - Where SSH reaches the Pi, as user@host.
    @param into - pathlib.Path of a local directory, which gets one directory
      per run.
    @param runs - How many starts.
    @param seconds - How long each capture runs after the emulator started.
    @param machine - A machine from the admin's catalogue to measure instead of
      the one configured, or None. The configuration is put back afterwards.
    @returns list of pathlib.Path, one directory per run.
    """
    _put_code(target)
    _install_unit(target, seconds)
    directories = []
    try:
        if machine is not None:
            _switch(target, machine)
        for run in range(1, runs + 1):
            say("%s: start %d of %d" % (target, run, runs))
            _ssh(target, "rm -rf %s" % REMOTE_RUN)
            _reboot(target)
            _wait_for_capture(target, seconds)
            directory = into / ("run-%d" % run)
            _collect(target, directory)
            directories.append(directory)
    finally:
        if machine is not None:
            _switch_back(target)
        _remove(target)
    return directories


def _put_code(target):
    """Copies the capture and the package it imports onto the Pi."""
    _ssh(target, "rm -rf %s && mkdir -p %s" % (REMOTE_CODE, REMOTE_CODE))
    _run(["scp", "-q", "-r", str(PACKAGE), str(HERE / "capture.py"),
          "%s:%s/" % (target, REMOTE_CODE)])


def _install_unit(target, seconds):
    """Writes the user unit and enables it, so the next login starts it."""
    unit = (
        "[Unit]\n"
        "Description=Previously: one measured start of the emulator\n"
        "\n"
        "[Service]\n"
        "Type=exec\n"
        "ExecStart=/usr/bin/python3 -I %%h/%s/capture.py %%h/%s %d\n"
        "\n"
        "[Install]\n"
        "WantedBy=default.target\n" % (REMOTE_CODE, REMOTE_RUN, seconds))
    _ssh(target, "mkdir -p .config/systemd/user && cat > %s" % UNIT_PATH, unit)
    _ssh(target, "systemctl --user daemon-reload && systemctl --user enable %s" % UNIT)


def _switch(target, machine):
    """Keeps the configuration as it is and makes the emulator that machine,
    the way the admin's machine window does.

    @raises RuntimeError where the Pi refuses, because measuring on would
      measure the machine that was there before under the other one's name.
    """
    _ssh(target, "cp .config/previous/previous.cfg %s" % REMOTE_CONFIGURATION)
    ok, said = json.loads(_python(
        target, "import json\nfrom previously import change, settings\n"
                "print(json.dumps(change.to_machine(%r, settings.Settings.load())))\n"
                % machine))
    if not ok:
        raise RuntimeError("%s did not become %s: %s" % (target, machine, said))
    say("%s: %s" % (target, said))


def _switch_back(target):
    """Puts the configuration kept by `_switch` back and restarts the guest."""
    _ssh(target, "cp %s .config/previous/previous.cfg" % REMOTE_CONFIGURATION)
    _python(target, "from previously import kiosk, settings; "
                    "print(kiosk.restart(settings.Settings.load().runtime_directory))")


def _reboot(target):
    """Restarts the board through the admin and waits until it answers again.

    @raises RuntimeError where it does not come back in time.
    """
    before = _boot_id(target)
    _python(target, "from previously import kiosk, settings; "
                    "print(kiosk.board('reboot', "
                    "settings.Settings.load().runtime_directory))")
    until = time.monotonic() + BACK_WITHIN_SECONDS
    while time.monotonic() < until:
        time.sleep(ASK_EVERY_SECONDS)
        now = _boot_id(target, quiet=True)
        if now and now != before:
            return
    raise RuntimeError("%s did not come back within %d seconds"
                       % (target, BACK_WITHIN_SECONDS))


def _boot_id(target, quiet=False):
    """@returns The kernel's id for this boot, or "" where SSH did not answer."""
    return _ssh(target, "cat /proc/sys/kernel/random/boot_id", quiet=quiet).strip()


def _wait_for_capture(target, seconds):
    """Waits until the capture has written its record."""
    until = time.monotonic() + seconds + BACK_WITHIN_SECONDS
    while time.monotonic() < until:
        if _ssh(target, "test -f %s/done && echo done" % REMOTE_RUN, quiet=True):
            return
        time.sleep(ASK_EVERY_SECONDS)
    raise RuntimeError("%s: the capture did not finish" % target)


def _collect(target, directory):
    """Fetches what the capture wrote and what systemd says about the boot."""
    directory.mkdir(parents=True, exist_ok=True)
    _run(["scp", "-q", "-r", "%s:%s/." % (target, REMOTE_RUN), str(directory)])
    for name, command in (("systemd-analyze.txt", "systemd-analyze"),
                          ("critical-chain.txt", "systemd-analyze critical-chain"),
                          ("blame.txt", "systemd-analyze blame")):
        (directory / name).write_text(_ssh(target, command))


def _remove(target):
    """Stops a capture that is still running and takes the unit and every file
    this put on the Pi away again.

    @raises CalledProcessError where the Pi does not answer, so nothing is
      left behind without whoever runs this hearing about it.
    """
    _ssh(target, "systemctl --user disable --now %s; rm -f %s; "
                 "systemctl --user daemon-reload; rm -rf %s"
                 % (UNIT, UNIT_PATH, REMOTE))


def _python(target, program):
    """@returns What Python printed on the Pi, run against the copy.

    The program goes in on stdin, so no quote in it has to survive the shell
    on the Pi.
    """
    return _ssh(target, "%s -" % REMOTE_PYTHON, program)


def _ssh(target, command, given=None, quiet=False):
    """Runs a command on the Pi.

    @param given - Text to hand it on stdin, or None.
    @param quiet - Whether a failure is an answer of "" rather than an error,
      which is what asking a board that is still starting comes to.
    @returns str, what it printed.
    """
    try:
        return _run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5", target,
                     command], given)
    except subprocess.CalledProcessError:
        if quiet:
            return ""
        raise


def _run(command, given=None):
    """@returns str, what a local command printed. @raises CalledProcessError."""
    return subprocess.run(command, input=given, capture_output=True, text=True,
                          check=True).stdout


def say(line):
    """Tells whoever runs this what is happening, on stderr."""
    print(line, file=sys.stderr, flush=True)


# -- reading what was kept ---------------------------------------------------


def startup(text):
    """What `systemd-analyze` says about the boot.

    @param text - Its output.
    @returns dict with `kernel`, `userspace` and `multi_user`, in seconds, the
      last counted from the kernel's start. Any that is not there is None.
    """
    found = {"kernel": None, "userspace": None, "multi_user": None}
    kernel = re.search(r"in (.+?) \(kernel\)", text)
    userspace = re.search(r"\+ (.+?) \(userspace\)", text)
    multi_user = re.search(r"multi-user\.target reached after (.+?) in userspace", text)
    if kernel:
        found["kernel"] = seconds_in(kernel.group(1))
    if userspace:
        found["userspace"] = seconds_in(userspace.group(1))
    if multi_user and found["kernel"] is not None:
        found["multi_user"] = found["kernel"] + seconds_in(multi_user.group(1))
    return found


def seconds_in(span):
    """@returns float, a span systemd wrote such as "2min 7.783s" or "123ms"."""
    units = {"h": 3600, "min": 60, "s": 1, "ms": 0.001}
    return sum(float(amount) * units[unit]
               for amount, unit in re.findall(r"([\d.]+)(h|min|ms|s)\b", span))


def changed_pixels(one, other):
    """@returns int, how many pixels differ between two pictures."""
    difference = ImageChops.difference(one.convert("RGB"), other.convert("RGB"))
    return difference.convert("L").point(lambda value: 255 if value else 0).histogram()[255]


def first_picture(frames):
    """When the screen first showed anything other than one flat color.

    @param frames - list of (seconds, Image), in the order they were taken.
    @returns float, or None where it never did.
    """
    for at, picture in frames:
        low, high = picture.convert("L").getextrema()
        if low != high:
            return at
    return None


def settled(frames):
    """When the screen stopped changing, apart from the clock in the dock.

    @param frames - list of (seconds, Image), in the order they were taken.
    @returns float, the time of the first picture from which every later one
      looks like the last, or None where there are no pictures.

    Read backwards from the last picture, because the end of a boot is the one
    thing the capture is sure to hold.
    """
    if not frames:
        return None
    last = frames[-1][1]
    index = len(frames) - 1
    while index > 0 and changed_pixels(frames[index - 1][1], last) <= CLOCK_PIXELS:
        index -= 1
    return frames[index][0]


def load(samples, key, start, end, ticks_per_second, from_nothing=False):
    """How much of one core each name used between two moments.

    @param samples - The capture's samples, in order.
    @param key - "threads" or "processes".
    @param start - Seconds since boot.
    @param end - Seconds since boot.
    @param ticks_per_second - What the Pi counted a core's time in.
    @param from_nothing - Whether everything began at `start` with no time on a
      core, which is true of the emulator's threads from the emulator's start.
    @returns dict of name to percent of one core, summed over every thread or
      process of that name. Empty where the samples do not cover the span.
    """
    last = _nearest(samples, end, before=True)
    first = None if from_nothing else _nearest(samples, start, before=False)
    if last is None or (first is None and not from_nothing):
        return {}
    seconds = last["at"] - (start if from_nothing else first["at"])
    if seconds <= 0:
        return {}

    # One that the first sample does not hold started inside the span, so all
    # of its time is.
    spent = {}
    for number, (name, ticks) in last[key].items():
        before = 0 if from_nothing else first[key].get(number, [name, 0])[1]
        family = _family(name)
        spent[family] = spent.get(family, 0) + ticks - before
    return {name: round(ticks * 100 / (ticks_per_second * seconds), 1)
            for name, ticks in spent.items()}


def _family(name):
    """@returns The name a process is counted under: its own, or one line for
    all of the kernel's workers."""
    return KERNEL_WORKER if name.startswith(KERNEL_WORKER + "/") else name


def _nearest(samples, at, before):
    """@returns The last sample at or before a moment, or the first at or after
    it, or None."""
    if before:
        earlier = [sample for sample in samples if sample["at"] <= at]
        return earlier[-1] if earlier else None
    later = [sample for sample in samples if sample["at"] >= at]
    return later[0] if later else None


def read_run(directory):
    """Everything one start left behind, worked out.

    @param directory - pathlib.Path that `_collect` filled.
    @returns dict of figures, every time in seconds since the kernel started.
    """
    record = json.loads((directory / "capture.json").read_text())
    samples = record["samples"]
    per_second = record["ticks_per_second"]
    frames = [(frame["at"], Image.open(directory / "frames" / frame["file"]))
              for frame in record["frames"]]
    started = record["emulator"]["started_at"]
    done = settled(frames)
    idle = None if done is None else done + IDLE_AFTER_SECONDS
    end = samples[-1]["at"]
    figures = startup((directory / "systemd-analyze.txt").read_text())
    figures.update({
        "previous": started,
        "picture": first_picture(frames),
        "settled": done,
        "booting": None if done is None else done - started,
        "threads_booting": {} if done is None else load(
            samples, "threads", started, done, per_second, from_nothing=True),
        "threads_idle": {} if idle is None else load(
            samples, "threads", idle, end, per_second),
        "processes_booting": {} if done is None else load(
            samples, "processes", started, done, per_second),
        "processes_idle": {} if idle is None else load(
            samples, "processes", idle, end, per_second),
    })
    return figures


# -- the report ----------------------------------------------------------------


#: The columns of the timing table, as (heading, figure).
TIMES = (("Kernel", "kernel"), ("Userspace", "userspace"),
         ("multi-user.target", "multi_user"), ("Previous starts", "previous"),
         ("First picture", "picture"), ("Screen settled", "settled"),
         ("NeXTSTEP boot", "booting"))


def report(title, runs):
    """The figures of several starts as Markdown, one table each.

    @param title - What was measured, such as "Pi 5, NeXTcube Turbo".
    @param runs - What `read_run` returned for each start.
    @returns str
    """
    lines = ["### %s" % title, "",
             "Seconds since the kernel started. Userspace and NeXTSTEP boot are spans.",
             "",
             "| Run | %s |" % " | ".join(heading for heading, _ in TIMES),
             "|---|%s" % ("---:|" * len(TIMES))]
    for number, run in enumerate(runs, 1):
        figures = " | ".join(_seconds(run[key]) for _, key in TIMES)
        lines.append("| %d | %s |" % (number, figures))
    lines.append("| Median | %s |" % " | ".join(
        _seconds(_median([run[key] for run in runs])) for _, key in TIMES))

    lines += ["", "Percent of one core, median of the runs.", ""]
    lines += _load_table("Emulator thread", runs, "threads", None)
    lines += [""]
    lines += _load_table("Process", runs, "processes", PROCESSES_LISTED)
    return "\n".join(lines) + "\n"


def _load_table(heading, runs, key, listed):
    """@returns list of Markdown lines for one load table, busiest when idle
    first. Where `listed` is not None, that many rows and then every WATCHED
    process that is not among them, at 0 where it did not run."""
    names = set()
    for run in runs:
        names.update(run[key + "_booting"])
        names.update(run[key + "_idle"])
    rows = []
    for name in names:
        booting = _median([run[key + "_booting"].get(name) for run in runs])
        idle = _median([run[key + "_idle"].get(name) for run in runs])
        rows.append((idle or 0, booting or 0, name))
    rows.sort(reverse=True)
    if listed is not None:
        found = {row[2]: row for row in rows}
        rows = rows[:listed]
        shown = {row[2] for row in rows}
        rows += [found.get(name, (0, 0, name)) for name in WATCHED if name not in shown]
    lines = ["| %s | While booting | Idle |" % heading, "|---|---:|---:|"]
    lines += ["| `%s` | %.1f | %.1f |" % (name, booting, idle)
              for idle, booting, name in rows]
    return lines


def _median(values):
    """@returns The median of the values that are there, or None."""
    present = [value for value in values if value is not None]
    return statistics.median(present) if present else None


def _seconds(value):
    """@returns A figure for the table, or MISSING where there is none."""
    return MISSING if value is None else "%.1f" % value


def main(argv=None):
    """Measures a Pi, or reads what an earlier measurement kept."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("target", nargs="?", help="user@host of the Pi")
    parser.add_argument("--into", type=pathlib.Path, help="where to keep the runs")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--seconds", type=int, default=CAPTURE_SECONDS)
    parser.add_argument("--machine", help="a machine from the catalogue to measure")
    parser.add_argument("--title", help="the heading of the report")
    parser.add_argument("--report", type=pathlib.Path,
                        help="read the runs kept in this directory and measure nothing")
    arguments = parser.parse_args(argv)

    if arguments.report is not None:
        directories = sorted(arguments.report.glob("run-*"))
        title = arguments.title or arguments.report.name
    else:
        if arguments.target is None or arguments.into is None:
            parser.error("a target and --into are needed to measure")
        directories = measure(arguments.target, arguments.into, arguments.runs,
                              arguments.seconds, arguments.machine)
        title = arguments.title or arguments.target

    print(report(title, [read_run(directory) for directory in directories]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
