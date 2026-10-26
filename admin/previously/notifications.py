"""What is worth telling whoever has the admin open, decided on the Pi.

Three things the service already knows are worth saying to somebody who is not
looking at the window that shows them: a newer release of this tool, a newer
Previous in the archive it comes from, and a board in a state worth acting on.
This module is the one place that decides which readings become a
notification, and every browser draws what it answers.

It answers with names, levels and values rather than with sentences, as every
answer of this service does, because a sentence written here could only ever
be in one language.

It also keeps what it decides on fresh. The windows ask GitHub and the archive
only while somebody has them open, so a thread started with the service asks
both whenever what it knows has grown old.
"""

import threading
import time

from . import archive, kiosk, pi, release, setup

#: How full the card may be before it is said. The disk images and the shared
#: directory both live on it, and above this an unpack can run out of room part
#: way through.
DISK_FULL_PERCENT = 90

#: How old what is known about the newest release and the newest Previous may
#: be before it is asked again. An hour costs one of the sixty requests an
#: address may make to GitHub in that time.
FRESH_SECONDS = 3600

#: How often the watch wakes to see whether anything has grown old. Short, so a
#: Pi that started before its network was up learns both within minutes of it
#: coming up rather than an hour later.
TICK_SECONDS = 300


class Level:
    """How much a notification matters, which the page draws as its picture."""

    INFO = "info"
    ALERT = "alert"
    ERROR = "error"


#: Whether the watch is running, so a second start does not make a second one.
_WATCHING = False
_STARTING = threading.Lock()


def watch():
    """Starts the thread that keeps the newest release and Previous fresh.

    Once per service. It lives as long as the service does, and a daemon thread
    is what lets the service stop without waiting for it.
    """
    global _WATCHING
    with _STARTING:
        if _WATCHING:
            return
        _WATCHING = True
    threading.Thread(target=_watching, name="notifications", daemon=True).start()


def look_again(now=None):
    """Asks GitHub and the archive again, each where what is known is missing
    or older than FRESH_SECONDS.

    @param now - The moment to measure against, for a test. None means the
      clock.

    Neither ask waits. Each starts a lookup in a thread of its own, under the
    floor its module keeps, and what comes back is there for the next answer.
    """
    moment = now or time.time()
    for asked in (release.published, archive.offered):
        known = asked()
        if known is None or moment - known["asked_at"] >= FRESH_SECONDS:
            asked(check=True)


def current(settings):
    """What is worth saying now, read off this machine.

    @param settings - Settings, for where the helper and the console write.
    @returns list of notifications as `worth_saying` makes them.
    """
    published = release.published()
    installed = setup.version_of(release.PACKAGE)
    newest = archive.offered()
    emulator_here = setup.installed(setup.EMULATOR_PACKAGE)
    emulator = setup.version_of(setup.EMULATOR_PACKAGE) if emulator_here else None
    progress = kiosk.setting_up(settings.setup_directory)
    return worth_saying(
        tool={"installed": installed,
              "published": published["version"] if published else None},
        emulator={"version": emulator,
                  "newest": newest["version"] if newest else None},
        board=pi.readings(settings.runtime_directory),
        running=bool(progress) and progress.get("finished_at") is None,
    )


def worth_saying(tool, emulator, board, running):
    """Which readings become a notification.

    @param tool - dict with `installed` and `published`, this tool's versions as
      dpkg and GitHub give them, either None where it is not known.
    @param emulator - dict with `version` and `newest`, Previous as dpkg has it
      and as the archive offers it, `version` None where it is not installed.
    @param board - dict as `pi.readings` answers.
    @param running - Whether the helper is in the middle of a job.
    @returns list of dicts, each with `name`, `level`, `reading` and `values`.
      `name` says which notification it is and is what the page keys its words
      by. `reading` is what has to change for one that somebody closed to come
      back: the version on offer, the number of crashes, or nothing where the
      condition going and coming again is what brings it back.

    Neither update is offered while the helper is busy. It takes one job at a
    time, and the window that started the job is already saying how it goes.
    """
    said = []

    def say(name, level, reading="", **values):
        said.append({"name": name, "level": level, "reading": reading,
                     "values": values})

    if not running:
        if setup.newer_than(tool["installed"], tool["published"]):
            say("update", Level.INFO, tool["published"],
                version=tool["published"], installed=tool["installed"])
        if setup.newer_than(emulator["version"], emulator["newest"]):
            say("emulator", Level.INFO, emulator["newest"],
                version=emulator["newest"], installed=emulator["version"])

    throttling = board.get("throttling") or {}
    if "under-voltage" in throttling.get("now", []):
        say("power", Level.ALERT)

    temperature = board.get("temperature_c")
    if temperature is not None and temperature >= pi.TEMPERATURE_LIMIT_C:
        say("temperature", Level.ALERT, temperature=round(temperature),
            limit=pi.TEMPERATURE_LIMIT_C)

    disk = board.get("disk")
    if disk and disk["used_percent"] >= DISK_FULL_PERCENT:
        say("disk", Level.ALERT, percent=disk["used_percent"],
            free_mb=disk["free_mb"])

    crashes = board.get("crashes")
    if crashes:
        say("crash", Level.ERROR, str(crashes["count"]),
            count=crashes["count"], last=crashes["last"])

    return said


def _watching():
    """Looks again for as long as the service runs."""
    while True:
        look_again()
        time.sleep(TICK_SECONDS)
