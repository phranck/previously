"""Looking for a newer release of this tool and a newer Previous, on the Pi.

The windows ask GitHub and the archive only while somebody has them open, so a
thread started with the service asks both whenever what it knows has grown
old. Whoever runs the Pi decides in Preferences whether it does: looking
automatically is the watch below, and looking manually leaves it to the Check
Now button in that module and to opening the Raspberry Pi window or the
Installer, which ask as they always have.

The choice belongs to the Pi rather than to one browser, because the Pi is what
looks, so it is kept in the service's own state directory.
"""

import json
import threading
import time

from . import archive, release

#: How old what is known about the newest release and the newest Previous may
#: be before it is asked again. An hour costs one of the sixty requests an
#: address may make to GitHub in that time.
FRESH_SECONDS = 3600

#: How often the watch wakes to see whether anything has grown old. Short, so a
#: Pi that started before its network was up learns both within minutes of it
#: coming up rather than an hour later.
TICK_SECONDS = 300

#: The file in the state directory that keeps the choice.
CHOICE = "updates.json"

#: Whether the watch is running, so a second start does not make a second one.
_WATCHING = False
_STARTING = threading.Lock()


def automatic(state_directory):
    """Whether the Pi looks for updates on its own.

    @param state_directory - pathlib.Path the service keeps its own state in.
    @returns bool. True where nothing was chosen or the file cannot be read,
      because looking is what a Pi does until somebody says otherwise.
    """
    try:
        kept = json.loads((state_directory / CHOICE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return True
    return kept.get("automatic") is not False if isinstance(kept, dict) else True


def choose(state_directory, looks_on_its_own):
    """Keeps whether the Pi looks for updates on its own.

    @param state_directory - pathlib.Path the service keeps its own state in.
    @param looks_on_its_own - bool.
    @raises OSError where the file cannot be written.

    Written beside and then moved over the old file, so a reader never meets
    half a choice.
    """
    path = state_directory / CHOICE
    written = path.with_suffix(".json.new")
    written.write_text(json.dumps({"automatic": bool(looks_on_its_own)}), encoding="utf-8")
    written.replace(path)


def look_now():
    """Asks GitHub and the archive once, at once, whatever is known.

    Neither ask waits, and each keeps the floor its own module puts under how
    often a host is asked, so a button pressed twice in a breath asks once.
    """
    release.published(check=True)
    archive.offered(check=True)


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


def watch(state_directory):
    """Starts the thread that keeps the newest release and Previous fresh.

    @param state_directory - pathlib.Path the choice is kept in, read at every
      tick so a change in Preferences takes effect without a restart.

    Once per service. It lives as long as the service does, and a daemon thread
    is what lets the service stop without waiting for it.
    """
    global _WATCHING
    with _STARTING:
        if _WATCHING:
            return
        _WATCHING = True
    threading.Thread(target=_watching, args=(state_directory,), name="updates",
                     daemon=True).start()


def _watching(state_directory):
    """Looks again for as long as the service runs, where the Pi is to."""
    while True:
        if automatic(state_directory):
            look_again()
        time.sleep(TICK_SECONDS)
