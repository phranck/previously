"""Which Previous the archive it comes from offers, read off the archive itself.

apt answers the same question out of the package lists it keeps, and those are
only as new as the last time something refreshed them. On this machine that is
the system's own daily timer, which can be switched off, and then a newer
Previous is never seen. So the service reads the archive's index directly.

What is read here decides only whether anything is said. Installing still goes
through apt, which refreshes its lists and checks the archive's signature
before it puts a package in place, so an index read without that signature
can at worst raise a notification that the Installer then has nothing to
install for.
"""

import gzip
import io
import re
import threading
import time
import urllib.error
import urllib.parse

from . import fetching, setup

#: The archive's index of packages for this board, on the archive and on its
#: copy on previous.li, asked in that order. The source the setup writes names
#: `main` alone.
INDEXES = tuple("%s/dists/%s/main/binary-%s/Packages.gz"
                % (base, setup.REPOSITORY_SUITE, setup.ARCHITECTURE)
                for base in (setup.REPOSITORY_URL, setup.REPOSITORY_COPY_URL))

#: The two hosts those addresses are on, and nothing else.
HOSTS = tuple(urllib.parse.urlparse(index).hostname for index in INDEXES)

#: How long to wait for either. The index is twenty kilobytes.
TIMEOUT_SECONDS = 20

#: The most of the compressed index to read, and the most it may unpack to. It
#: is twenty kilobytes and sixty-four unpacked, so these bound an answer that
#: is not an index rather than one that has grown.
LARGEST_INDEX = 1024 * 1024
LARGEST_UNPACKED = 16 * 1024 * 1024

#: The least time between two lookups, whoever asks for one, as release.py
#: keeps for GitHub.
SOONEST_SECONDS = 20

#: One stanza's name and version, which is all that is read of it.
FIELD = re.compile(r"^(Package|Version):\s*(\S+)\s*$", re.M)

#: The last answer, when the archive was last asked at all, and one lookup at a
#: time. The moment is kept apart from the answer for the reason release.py
#: gives: a board whose network is down learns nothing, and without it every
#: ask would start another lookup.
_KNOWN = None
_ASKED_AT = 0.0
_LOOKING = threading.Lock()


class Unreachable(Exception):
    """Neither host could be asked, or what came back is not an index."""


def offered(check=False, now=None):
    """The newest Previous the archive offers, without waiting for it.

    @param check - Whether to ask the archive again behind this answer.
    @param now - The moment to measure the floor against, for a test. None means
      the clock.
    @returns dict with `version` and `asked_at`, or None where nothing has been
      learned yet, which is the ordinary state of the first seconds after the
      service starts and of a machine with no internet.
    """
    if check and (now or time.time()) - _ASKED_AT >= SOONEST_SECONDS:
        _look_behind_this()
    known = _KNOWN
    return dict(known) if known else None


def look():
    """Asks the archive, and then its copy, for the newest Previous.

    @returns dict as `offered` describes it.
    @raises Unreachable where neither answered with an index naming Previous.
    """
    for index in INDEXES:
        try:
            with fetching.opened(index, HOSTS, TIMEOUT_SECONDS) as answer:
                packed = answer.read(LARGEST_INDEX)
            text = _unpacked(packed).decode("utf-8", "replace")
        except (urllib.error.URLError, OSError, EOFError, ValueError):
            continue
        version = newest_in(text, setup.EMULATOR_PACKAGE)
        if version:
            found = {"version": version, "asked_at": time.time()}
            global _KNOWN
            _KNOWN = dict(found)
            return found
    raise Unreachable("no index named %s" % setup.EMULATOR_PACKAGE)


def newest_in(index, package):
    """The newest version of one package an index lists.

    @param index - A Packages file as text, one stanza per package version.
    @param package - The package's name.
    @returns str, or None where the index does not list it. The archive keeps
      every version it has published, so the newest is chosen by dpkg's own
      ordering rather than by where it stands.
    """
    newest = None
    name = None
    for field, value in FIELD.findall(index):
        if field == "Package":
            name = value
        elif name == package and (newest is None or setup.newer_than(newest, value)):
            newest = value
    return newest


def forget():
    """Throws the answer and the floor under it away, for a test."""
    global _KNOWN, _ASKED_AT
    _KNOWN = None
    _ASKED_AT = 0.0


def _unpacked(packed):
    """@returns bytes, the index unpacked, refusing one that grows past
    LARGEST_UNPACKED."""
    with gzip.GzipFile(fileobj=io.BytesIO(packed)) as reader:
        unpacked = reader.read(LARGEST_UNPACKED + 1)
    if len(unpacked) > LARGEST_UNPACKED:
        raise ValueError("an index larger than any this archive has")
    return unpacked


def _look_behind_this():
    """Asks the archive again in a thread, where nothing is already asking."""
    def stamp():
        global _ASKED_AT
        _ASKED_AT = time.time()

    fetching.in_the_background(_LOOKING, stamp, look, Unreachable)
