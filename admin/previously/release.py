"""Which release of this tool is published, and where its package is.

The tool cannot say whether it is out of date without asking somebody, and the
somebody is the repository it is released from. This module is the whole of that
conversation: one address, one answer, and what came back kept for a while.

Nothing here waits. `published` answers with what is already known and looks
again in a thread where that has got old, because the window asking is polled
every five seconds and a board with no internet would otherwise hold each
reading up for as long as a connection takes to fail.

What the answer is checked for matters more than it looks. The download address
arrives inside it, so it is somebody else's value reaching a fetch, and the size
and the digest beside it are what the privileged helper refuses a package
against. A field that is missing, the wrong type or absurdly large is an answer
this does not understand, and an answer this does not understand offers no
update at all.
"""

import json
import re
import threading
import time
import urllib.error

from . import fetching

#: Where this tool is released from, and what its package is called there. The
#: package name is also what dpkg knows it by, which is what an update is
#: compared against, and `tests/test_packaging.py` holds the two together.
OWNER = "phranck"
REPOSITORY = "previously"
PACKAGE = "previously"

#: Which release to ask about. GitHub's own documentation says this endpoint
#: never answers with a draft and skips a prerelease, which is why neither is
#: checked for below.
#: https://docs.github.com/en/rest/releases/releases#get-the-latest-release
NEWEST = "https://api.github.com/repos/%s/%s/releases/latest" % (OWNER, REPOSITORY)

#: What the package is called on a release. `.github/workflows/release.yml`
#: attaches it under this name with no version in it, which is what makes one
#: address always the newest one.
ASSET = "previously_all.deb"

#: Which hosts asking and fetching may reach. The API is the first, the download
#: address it answers with is on the second, and GitHub redirects that download
#: to the third, so all three are needed and nothing else is.
HOSTS = ("api.github.com", "github.com", "githubusercontent.com")

#: What to send. GitHub asks for a version of its API by name rather than
#: leaving it to whatever is current, and it refuses a request with no
#: User-Agent at all.
HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent": REPOSITORY,
}

#: How long to wait. Slower than this is a board whose network is not working
#: rather than one that is busy, and the answer is a few kilobytes.
TIMEOUT_SECONDS = 20

#: The most of that answer to read. A release carries its whole description, so
#: this is generous, and it is here so that a reply which never ends is not read
#: until the memory runs out.
LARGEST_ANSWER = 1024 * 1024

#: The most a package may say it is. This tool's own is a quarter of a megabyte,
#: so anything past this is not it, and the figure is what a progress bar and a
#: download are sized from.
LARGEST_PACKAGE = 64 * 1024 * 1024

#: The least time between two lookups, whoever asks for one. Three a minute,
#: which is what opening the Raspberry Pi window is allowed to cost.
#:
#: It is a floor rather than an age, because what asks is a person opening a
#: window rather than a loop: the window's own poll reads what is known and asks
#: for nothing. Three a minute sustained would be a hundred and eighty an hour
#: against the sixty an address is allowed unauthenticated, so a poll that asked
#: would stop working part way through an afternoon and say nothing about it.
#:
#: A conditional request does not buy that back. Measured against
#: api.github.com on 29 September 2026: an `If-None-Match` answered `304` and
#: `x-ratelimit-remaining` still fell by one each time, 49 to 48 to 47. So the
#: floor is the whole mechanism.
SOONEST_SECONDS = 20

#: What GitHub states an asset's digest as, which is the algorithm and the hex,
#: and the algorithm on its own for the fetch that checks it. Beside the pattern
#: rather than at the place the check happens, because it is a fact about what
#: GitHub publishes.
ALGORITHM = "sha256"
DIGEST = re.compile(r"^%s:([0-9a-f]{64})$" % ALGORITHM)

#: What a version tag looks like, so `v1.0.0` becomes the `1.0.0` dpkg knows.
TAG = re.compile(r"^v?(\d[\w.+~-]*)$")

#: The last answer, when GitHub was last asked anything at all, and one lookup
#: at a time.
#:
#: The moment is kept apart from the answer because it is about attempts rather
#: than about successes: a board whose network is down learns nothing, and
#: without this every ask would set off another lookup with no floor under it.
_KNOWN = None
_ASKED_AT = 0.0
_LOOKING = threading.Lock()


class Unreachable(Exception):
    """GitHub could not be asked, or said something this does not understand."""


def published(check=False, now=None):
    """What the newest release is, without waiting for GitHub.

    @param check - Whether to ask GitHub again behind this answer. True where
      somebody opened the window that shows it, and False where a poll is only
      redrawing what is already on the screen.
    @param now - The moment to measure the floor against, for a test. None means
      the clock.
    @returns dict as `look` describes it, or None where nothing has been learnt
      yet. None is not an error: it is the ordinary state of the first seconds
      after this service starts, and of a machine with no internet.

    Asking never holds this up. The lookup runs in a thread and this answers
    with what is known, so the first open of the window draws nothing for a
    second and everything after it draws what came back.
    """
    if check and (now or time.time()) - _ASKED_AT >= SOONEST_SECONDS:
        _look_behind_this()
    known = _KNOWN
    return dict(known) if known else None


def look():
    """Asks GitHub what the newest release is.

    @returns dict with `version`, `url`, `size`, `digest` and `asked_at`. The
      digest is the hex alone, because the algorithm is in the name of the field
      it is checked with.
    @raises Unreachable where GitHub could not be asked or answered with
      something this does not understand.

    Blocking, which is why the service calls `published` instead. The privileged
    helper calls this one: it is already a program somebody is watching a
    progress bar for, and it has nothing to answer in the meantime.
    """
    try:
        with fetching.opened(NEWEST, HOSTS, TIMEOUT_SECONDS, HEADERS) as answer:
            said = json.loads(answer.read(LARGEST_ANSWER))
    except (urllib.error.URLError, OSError, ValueError) as error:
        raise Unreachable("cannot ask GitHub") from error

    found = _understood(said)
    found["asked_at"] = time.time()
    global _KNOWN
    _KNOWN = dict(found)
    return found


def forget():
    """Throws that answer and the floor under it away, for a test.

    A test that left either behind would be one test's machine answering
    another test's question, or one refusing to ask at all.
    """
    global _KNOWN, _ASKED_AT
    _KNOWN = None
    _ASKED_AT = 0.0


def _understood(said):
    """What a release means, or a refusal.

    @param said - What GitHub answered, parsed.
    @returns dict with `version`, `url`, `size` and `digest`.
    @raises Unreachable where any of the four is missing or is not what it has
      to be.

    Every field is somebody else's value, and the one that matters most is the
    address: it reaches a fetch, so it is checked against the same hosts that
    fetch is allowed rather than trusted for having come from an answer this
    asked for.
    """
    if not isinstance(said, dict):
        raise Unreachable("not a release")

    tag = TAG.match(str(said.get("tag_name") or ""))
    if not tag:
        raise Unreachable("no version in the tag")

    for asset in said.get("assets") or []:
        if isinstance(asset, dict) and asset.get("name") == ASSET:
            return {"version": tag.group(1), **_the_package(asset)}
    raise Unreachable("no %s on that release" % ASSET)


def _the_package(asset):
    """The three facts about the file, checked.

    @param asset - One entry of a release's assets.
    @returns dict with `url`, `size` and `digest`.
    @raises Unreachable where one of them is not usable.
    """
    url = asset.get("browser_download_url")
    if not isinstance(url, str) or not fetching.allowed(url, HOSTS):
        raise Unreachable("the download address is not one this may ask")

    size = asset.get("size")
    if not isinstance(size, int) or isinstance(size, bool) \
            or not 0 < size <= LARGEST_PACKAGE:
        raise Unreachable("the package is not a size this expects")

    digest = DIGEST.match(str(asset.get("digest") or ""))
    if not digest:
        raise Unreachable("the package carries no sha256")

    return {"url": url, "size": size, "digest": digest.group(1)}


def _look_behind_this():
    """Looks again in a thread, where nothing is already looking.

    The moment is written down before the thread starts rather than after it
    finishes, because the floor is about how often GitHub is asked and a lookup
    that takes twenty seconds to time out is still a lookup that happened.
    """
    global _ASKED_AT
    if not _LOOKING.acquire(blocking=False):
        return
    _ASKED_AT = time.time()

    def asking():
        try:
            look()
        except Unreachable:
            # Nothing to do about it here. What is known stays known, or stays
            # unknown, and the reading says so by being absent.
            pass
        finally:
            _LOOKING.release()

    threading.Thread(target=asking, daemon=True).start()
