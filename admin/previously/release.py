"""Which release of this tool is published, and where its package is.

The tool cannot say whether it is out of date without asking somebody, and the
somebody is the repository it is released from. This module is the whole of that
conversation: the newest release, which an update is made from, the list of
every release, which only the notes are read from, and what came back from each
kept for a while.

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

#: Every release, for reading the notes of the ones before the newest. The same
#: API lists them newest first, and leaves drafts out for anybody not signed in
#: to the repository, which this service never is. One page holds a hundred,
#: which is more releases than this tool will have for a long while.
#: https://docs.github.com/en/rest/releases/releases#list-releases
EVERY = "https://api.github.com/repos/%s/%s/releases?per_page=100" % (OWNER, REPOSITORY)

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

#: The most of the list of every release to read. Each release in it carries its
#: notes and its assets, a few kilobytes, so a hundred of them fit well inside
#: this.
LARGEST_LIST = 4 * 1024 * 1024

#: The most a package may say it is. This tool's own is a quarter of a megabyte,
#: so anything past this is not it, and the figure is what a progress bar and a
#: download are sized from.
LARGEST_PACKAGE = 64 * 1024 * 1024

#: The most of a release's notes to keep. They are written to be read in one
#: sitting, and this is several times the longest that have been, so what it
#: bounds is a release whose notes are not notes. Anything past it is cut rather
#: than refused, because notes that are too long are still notes and refusing
#: them would take the update with them.
LONGEST_NOTES = 64 * 1024

#: How a release carries its notes in a language other than English: after the
#: English ones, one block per language, which GitHub shows collapsed under the
#: language's own name. The code is the one the interface's catalogs answer to,
#: so the German notes are in `<details lang="de">`.
TRANSLATION = re.compile(
    r'<details lang="([a-z]{2})">\s*<summary>.*?</summary>(.*?)</details>', re.S)

#: Where a paragraph ends in Markdown, which is at a blank line.
PARAGRAPH_END = re.compile(r"\n[ \t]*\n")

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

#: The same three for the list of every release, which is asked for apart from
#: the newest because the update reads nothing from it.
_HISTORY = None
_HISTORY_ASKED_AT = 0.0
_LOOKING_BACK = threading.Lock()


class Unreachable(Exception):
    """GitHub could not be asked, or said something this does not understand."""


def published(check=False, now=None):
    """What the newest release is, without waiting for GitHub.

    @param check - Whether to ask GitHub again behind this answer. True where
      somebody opened the window that shows it, and False where a poll is only
      redrawing what is already on the screen.
    @param now - The moment to measure the floor against, for a test. None means
      the clock.
    @returns dict as `look` describes it, or None where nothing has been learned
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

    @returns dict with `version`, `notes`, `url`, `size`, `digest` and
      `asked_at`. The digest is the hex alone, because the algorithm is in the
      name of the field it is checked with, and the notes are the release's own
      description as Markdown, which is what GitHub keeps them as.
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


def history(check=False, now=None):
    """Every published release's version and notes, without waiting for GitHub.

    @param check - Whether to ask GitHub behind this answer where the list is
      out of date. True where somebody is about to read notes.
    @param now - The moment to measure the floor against, for a test.
    @returns list of dicts with `version` and `notes`, newest first, and empty
      where nothing has been learned yet.

    Out of date means missing, or not holding the newest release `published`
    knows of. A published release's notes are read far more often than they
    change, so asking for them all at every reading would spend the requests an
    address is allowed on the same answer, and a release that is new is exactly
    what makes the list worth asking for again. The floor `published` keeps
    holds here as well.
    """
    newest = _KNOWN["version"] if _KNOWN else None
    known = _HISTORY or []
    stale = not known or (newest is not None
                          and newest not in {entry["version"] for entry in known})
    if check and stale and (now or time.time()) - _HISTORY_ASKED_AT >= SOONEST_SECONDS:
        _look_back_behind_this()
    return [dict(entry) for entry in (_HISTORY or [])]


def look_back():
    """Asks GitHub for every published release's version and notes.

    @returns list as `history` describes it.
    @raises Unreachable where GitHub could not be asked or answered with
      something that is not a list.

    A release in the list that is a draft, a prerelease or carries no version
    in its tag is left out rather than refusing the rest: these are notes to
    read, and nothing in them reaches a fetch.
    """
    try:
        with fetching.opened(EVERY, HOSTS, TIMEOUT_SECONDS, HEADERS) as answer:
            said = json.loads(answer.read(LARGEST_LIST))
    except (urllib.error.URLError, OSError, ValueError) as error:
        raise Unreachable("cannot ask GitHub") from error
    if not isinstance(said, list):
        raise Unreachable("not a list of releases")

    found = []
    for entry in said:
        if isinstance(entry, dict) and not entry.get("draft") \
                and not entry.get("prerelease"):
            read = _version_and_notes(entry)
            if read:
                found.append({"version": read[0], "notes": read[1]})
    global _HISTORY
    _HISTORY = [dict(entry) for entry in found]
    return found


def notes_in(notes, language):
    """A release's notes in one language.

    @param notes - The release's whole description, as `look` keeps it.
    @param language - Which language, by the code the interface names it with,
      such as "de".
    @returns str, the block written in that language, or the English notes
      where the release carries none in it. The English notes are the
      description with every block taken out, because that is where GitHub
      shows them and what a reader there sees first.
    """
    for code, text in TRANSLATION.findall(notes):
        if code == language:
            return text.strip()
    return TRANSLATION.sub("", notes).strip()


def runs(every):
    """The releases as the notes window offers them, one entry per page of notes.

    @param every - Releases as `history` answers them, newest first.
    @returns list of lists of versions, newest first in both. A release is a
      list of its own, and neighbors whose English notes open with the same
      paragraph share one.

    The releases from 1.0.0 to 1.2.1 each describe the whole tool rather than
    what they changed, so their notes all open with the same paragraph about
    what Previously is, and offered one by one they are the same page ten
    times. They are found by that paragraph rather than listed here, because
    the notes are what makes them alike and a list would be a second record of
    it. The newest of them has the fullest notes, which is why it leads.
    """
    grouped = []
    opening_before = None
    for entry in every:
        opening = _opening(entry["notes"])
        if grouped and opening and opening == opening_before:
            grouped[-1].append(entry["version"])
        else:
            grouped.append([entry["version"]])
        opening_before = opening
    return grouped


def _opening(notes):
    """@returns str, the first paragraph of a release's English notes, or ""."""
    return PARAGRAPH_END.split(notes_in(notes, ""), maxsplit=1)[0].strip()


def forget():
    """Throws that answer and the floor under it away, for a test.

    A test that left either behind would be one test's machine answering
    another test's question, or one refusing to ask at all.
    """
    global _KNOWN, _ASKED_AT, _HISTORY, _HISTORY_ASKED_AT
    _KNOWN = None
    _ASKED_AT = 0.0
    _HISTORY = None
    _HISTORY_ASKED_AT = 0.0


def _version_and_notes(said):
    """The version a release's tag names, and its notes.

    @param said - One release as GitHub describes it.
    @returns (version, notes), or None where the tag names no version. Notes
      that are missing or not text are "", because a release published without
      any is still a release, and notes too long to be notes are cut.
    """
    tag = TAG.match(str(said.get("tag_name") or ""))
    if not tag:
        return None
    body = said.get("body")
    return tag.group(1), body[:LONGEST_NOTES] if isinstance(body, str) else ""


def _understood(said):
    """What a release means, or a refusal.

    @param said - What GitHub answered, parsed.
    @returns dict with `version`, `notes`, `url`, `size` and `digest`.
    @raises Unreachable where any of the four that matter is missing or is not
      what it has to be.

    Every field is somebody else's value, and the one that matters most is the
    address: it reaches a fetch, so it is checked against the same hosts that
    fetch is allowed rather than trusted for having come from an answer this
    asked for.

    The notes are the one field that is allowed to be missing, because a release
    published without any is a release, and the window says so rather than
    refusing to offer the update.
    """
    if not isinstance(said, dict):
        raise Unreachable("not a release")

    read = _version_and_notes(said)
    if not read:
        raise Unreachable("no version in the tag")
    version, notes = read

    for asset in said.get("assets") or []:
        if isinstance(asset, dict) and asset.get("name") == ASSET:
            return {"version": version, "notes": notes, **_the_package(asset)}
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
    """Looks again for the newest release in a thread, where nothing is already
    looking."""
    def stamp():
        global _ASKED_AT
        _ASKED_AT = time.time()

    fetching.in_the_background(_LOOKING, stamp, look, Unreachable)


def _look_back_behind_this():
    """Asks for every release in a thread, where nothing is already asking."""
    def stamp():
        global _HISTORY_ASKED_AT
        _HISTORY_ASKED_AT = time.time()

    fetching.in_the_background(_LOOKING_BACK, stamp, look_back, Unreachable)


