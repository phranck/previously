"""Downloads of the catalog's CD images into the owner's Software folder.

Everything Previously downloads for its owner lands in one folder of its own,
`Software` inside the documents folder, so the owner finds it in one place and
removing Previously knows where to look. The download is the service's rather
than the privileged helper's, because an entry's address may have been typed
into Preferences, and nothing that arrives from a browser reaches root as an
address.

What arrives is a third party's answer. It is read no further than one byte
past the entry's size, written under a name of its own, and kept only where
its size and digest are the entry's. The address and every redirect must stay
on the entry's own host and out of this network, as `fetching.opened` checks.

One download runs at a time, in a thread of the service, so it goes on while
no browser is open. It ends with the service, and what it left is cleared when
the service starts again.
"""

import hashlib
import os
import pathlib
import threading
import urllib.error
import urllib.parse

from . import fetching, software, systems
from .answers import told

#: The folder inside the documents folder that downloads land in.
FOLDER = "Software"

#: What a downloaded image is called after its entry's identifier, which is a
#: suffix `discs.SUFFIXES` offers to Insert.
DISC_SUFFIX = ".iso"

#: What an image is called while it arrives, which `discs.SUFFIXES` does not
#: offer, so half an image is never put in the machine.
PART = ".part"

#: How much is read at a time. Big enough that a 400 MB image is not a million
#: reads, small enough that the progress moves.
CHUNK = 1024 * 1024

#: How long the host may stay silent before the download gives up.
TIMEOUT_SECONDS = 60


class Downloads:
    """The one download that may run, and what came of the last one.

    @param documents - pathlib.Path of the owner's documents folder.
    @param open_address - Opens an address on some hosts and answers a file to
      read. `fetching.opened` with `only_public` where none is given.
    @param room - Answers the free bytes where a path is. `systems.room_beside`
      where none is given.
    @param begin - Runs the download. A thread of its own where none is given.

    Whatever an earlier run of the service left half written is removed here,
    because only the service writes it and nothing will finish it.
    """

    def __init__(self, documents, open_address=None, room=None, begin=None):
        self.documents = pathlib.Path(documents)
        self._open = open_address or _opened
        self._room = room or systems.room_beside
        self._begin = begin or _in_a_thread
        self._lock = threading.Lock()
        self._state = None
        self._name = ""
        _clear_leftovers(self.folder())

    def folder(self):
        """@returns pathlib.Path the downloads land in."""
        return self.documents / FOLDER

    def state(self):
        """What the download running or last run is doing.

        @returns dict with `entry`, the identifier, `done` and `of` in bytes,
          `running`, and `outcome`, the told answer it ended with or None
          while it runs. None where nothing has been downloaded since the
          service started.
        """
        with self._lock:
            return dict(self._state) if self._state else None

    def start(self, entry):
        """Starts downloading an entry's image.

        @param entry - software.Entry, out of the catalog.
        @returns told answer: `download.started`, or why it was refused.
        """
        if entry.kind != "disc":
            return told("download.not-a-disc", name=entry.name)
        hosts = _hosts_for(entry.address)
        if not fetching.allowed(entry.address, hosts):
            return told("download.not-allowed", name=entry.name)
        if downloaded(self.documents, entry):
            return told("download.already-there", name=entry.name)
        room = self._room(self.folder())
        if room is not None and room < entry.size:
            return told("download.no-room", name=entry.name, size=entry.size, free=room)

        with self._lock:
            if self._state and self._state["running"]:
                return told("download.busy", name=self._name)
            self._state = {"entry": entry.identifier, "done": 0, "of": entry.size,
                           "running": True, "outcome": None}
            self._name = entry.name
        self._begin(lambda: self._download(entry, hosts))
        return told("download.started", name=entry.name)

    def _download(self, entry, hosts):
        """Downloads one image, and keeps it where it is whole.

        @param entry - software.Entry.
        @param hosts - The hosts the address and its redirects may reach.
        """
        target = image_of(self.documents, entry)
        part = target.with_name(target.name + PART)
        outcome = told("download.failed", name=entry.name)
        try:
            self.folder().mkdir(parents=True, exist_ok=True)
            outcome = self._fetch(entry, hosts, part)
            if outcome is None:
                os.replace(part, target)
                outcome = told("download.finished", name=entry.name)
        except fetching.NotAllowed:
            outcome = told("download.not-allowed", name=entry.name)
        except (urllib.error.URLError, OSError):
            outcome = told("download.failed", name=entry.name)
        finally:
            part.unlink(missing_ok=True)
            with self._lock:
                self._state["running"] = False
                self._state["outcome"] = outcome

    def _fetch(self, entry, hosts, part):
        """Reads the answer into `part`, counting and hashing as it goes.

        @returns None where it is the entry's image, or the told answer that
          says why not.
        """
        digest = hashlib.new(entry.algorithm)
        done = 0
        with self._open(entry.address, hosts) as answer, open(part, "wb") as written:
            while done <= entry.size:
                chunk = answer.read(min(CHUNK, entry.size + 1 - done))
                if not chunk:
                    break
                done += len(chunk)
                digest.update(chunk)
                written.write(chunk)
                with self._lock:
                    self._state["done"] = min(done, entry.size)
        if done != entry.size:
            return told("download.wrong-size", name=entry.name, size=entry.size, got=done)
        if digest.hexdigest() != entry.digest:
            return told("download.wrong-digest", name=entry.name)
        return None


def image_of(documents, entry):
    """@returns pathlib.Path an entry's image is kept at, named by the entry
    and never by the address or the answer."""
    return pathlib.Path(documents) / FOLDER / (entry.identifier + DISC_SUFFIX)


def downloaded(documents, entry):
    """@returns pathlib.Path of an entry's image where it has been downloaded,
    or None."""
    path = image_of(documents, entry)
    return path if path.is_file() else None


def _hosts_for(address):
    """@returns tuple of the hosts a download from this address may reach:
    archive.org and its nodes for an address there, because archive.org
    answers a download from one of them, and the address's own host for any
    other."""
    if fetching.allowed(address, software.ARCHIVE_HOSTS):
        return tuple(software.ARCHIVE_HOSTS)
    return (urllib.parse.urlparse(address).hostname or "",)


def _opened(url, hosts):
    """@returns The answer for an address, which with its redirects has to stay
    on these hosts and out of this network."""
    return fetching.opened(url, hosts, TIMEOUT_SECONDS, only_public=True)


def _in_a_thread(work):
    """Runs a download in a thread of its own, which ends with the service."""
    threading.Thread(target=work, daemon=True).start()


def _clear_leftovers(folder):
    """Removes every half written image in the folder."""
    try:
        leftovers = list(folder.glob("*" + PART))
    except OSError:
        return
    for path in leftovers:
        path.unlink(missing_ok=True)
