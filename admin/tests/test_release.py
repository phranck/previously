"""What GitHub says about the newest release, and what of it is believed.

Nothing here reaches the network. What is tested is the reading of an answer,
because every field in one is somebody else's value and two of them decide what
root does next: the address a fetch is pointed at, and the digest a package is
refused against. An answer this half understood would be worse than none.
"""

import io
import json
import threading
import time

import pytest

from previously import release

#: What GitHub actually answered on 29 September 2026, cut down to the fields
#: this reads. Kept as a literal rather than built by a helper, so a test about
#: a missing field is visibly the same answer with that field taken out.
ANSWERED = {
    "tag_name": "v1.0.0",
    "assets": [{
        "name": "previously_all.deb",
        "size": 269770,
        "digest": ("sha256:7298d28c17d560ad4cc97906ab35ffbe2795130457f8374375"
                   "ef529bcdc293ad"),
        "browser_download_url": ("https://github.com/phranck/previously/"
                                 "releases/download/v1.0.0/previously_all.deb"),
    }],
}


@pytest.fixture
def answering(monkeypatch):
    """Makes GitHub answer whatever a test hands it.

    @returns a function taking what to answer with, which is an object to be
      sent as JSON, raw bytes, or an exception to raise instead.
    """
    def answers(said):
        def opened(url, hosts, timeout, headers=None):
            if isinstance(said, Exception):
                raise said
            body = (said if isinstance(said, bytes)
                    else json.dumps(said).encode("utf-8"))
            return io.BytesIO(body)

        monkeypatch.setattr(release.fetching, "opened", opened)
    return answers


# -- what an answer means -------------------------------------------------


def test_the_newest_release_is_read_out_of_the_answer(answering):
    answering(ANSWERED)

    found = release.look()

    assert found["version"] == "1.0.0"
    assert found["size"] == 269770
    assert found["digest"].startswith("7298d28c")
    assert len(found["digest"]) == 64
    assert found["url"].startswith("https://github.com/phranck/previously/")


def test_what_the_release_says_about_itself_is_kept(answering):
    """It comes with the answer that is already being read, so a second request
    for it would be a second answer to a question already answered."""
    answering({**ANSWERED, "body": "## Installing it\n\nOne line."})

    assert release.look()["notes"] == "## Installing it\n\nOne line."


@pytest.mark.parametrize("body", [None, "", 42, {"text": "no"}])
def test_a_release_that_says_nothing_about_itself_is_still_a_release(
        answering, body):
    """Notes are the one field allowed to be missing. Refusing the release for
    want of them would take the update with them, and the window says there are
    none rather than nothing at all."""
    answering({**ANSWERED, "body": body})

    assert release.look()["notes"] == ""


def test_notes_longer_than_notes_are_cut_rather_than_refused(answering):
    """What this bounds is a release whose description is not a description.
    Cut, because notes that are too long are still notes."""
    answering({**ANSWERED, "body": "x" * (release.LONGEST_NOTES + 500)})

    found = release.look()

    assert len(found["notes"]) == release.LONGEST_NOTES
    assert found["version"] == "1.0.0"


#: A release's description as a release carries it: the English notes where
#: GitHub shows them, and two other languages in the blocks GitHub shows
#: collapsed.
IN_THREE_LANGUAGES = """One fix.

## Fixed

- Something.

<details lang="de"><summary>Deutsch</summary>

Ein Fix.

## Behoben

- Etwas.

</details>
<details lang="fr"><summary>Français</summary>

Une correction.

</details>
"""

ENGLISH = "One fix.\n\n## Fixed\n\n- Something."


def test_the_notes_come_in_the_language_asked_for():
    """The interface speaks six languages, and notes in another one than the
    reader chose are notes the reader may not be able to read."""
    assert release.notes_in(IN_THREE_LANGUAGES, "de") \
        == "Ein Fix.\n\n## Behoben\n\n- Etwas."
    assert release.notes_in(IN_THREE_LANGUAGES, "fr") == "Une correction."


@pytest.mark.parametrize("language", ["en", "sv", "", "xx"])
def test_a_language_with_no_notes_of_its_own_gets_the_english_ones(language):
    """English is the one every release has, and without the blocks for the
    other languages, which would otherwise come along under it."""
    assert release.notes_in(IN_THREE_LANGUAGES, language) == ENGLISH


def test_notes_in_one_language_are_those_whatever_is_asked_for():
    """Every release before the notes were translated is like this."""
    assert release.notes_in("## Installing it\n\nOne line.", "de") \
        == "## Installing it\n\nOne line."


def test_the_v_of_a_tag_is_not_part_of_the_version(answering):
    """A tag is `v1.0.0` and dpkg knows the package as `1.0.0`, so a version
    carrying the v would compare as older than everything."""
    answering({**ANSWERED, "tag_name": "v1.2.3"})

    assert release.look()["version"] == "1.2.3"


@pytest.mark.parametrize("said", [
    "not an object",
    {"assets": []},
    {"tag_name": "", "assets": []},
    {"tag_name": "nightly", "assets": []},
])
def test_an_answer_with_no_version_in_it_is_no_answer(answering, said):
    answering(said)

    with pytest.raises(release.Unreachable):
        release.look()


def test_a_release_carrying_no_package_of_ours_is_refused(answering):
    """The workflow attaches it under one name with no version in it, which is
    what makes one address always the newest one. A release without it is one
    nothing can be installed from."""
    answering({**ANSWERED, "assets": [{**ANSWERED["assets"][0],
                                       "name": "something-else.deb"}]})

    with pytest.raises(release.Unreachable):
        release.look()


@pytest.mark.parametrize("url", [
    "https://example.com/previously_all.deb",
    "http://github.com/previously_all.deb",
    "file:///etc/passwd",
    None,
    42,
])
def test_a_download_address_off_those_hosts_is_refused(answering, url):
    """The address arrives inside somebody else's answer and is then handed to a
    fetch root makes, so whoever controls that answer would otherwise control
    where root goes."""
    asset = {**ANSWERED["assets"][0], "browser_download_url": url}
    answering({**ANSWERED, "assets": [asset]})

    with pytest.raises(release.Unreachable):
        release.look()


@pytest.mark.parametrize("size", [
    0, -1, None, "269770", True, release.LARGEST_PACKAGE + 1,
])
def test_a_package_of_a_size_this_does_not_expect_is_refused(answering, size):
    """The figure is what a download is measured against and what the file is
    then checked to be, so a missing one would pass anything and an absurd one
    would ask a Pi to fetch it."""
    answering({**ANSWERED,
               "assets": [{**ANSWERED["assets"][0], "size": size}]})

    with pytest.raises(release.Unreachable):
        release.look()


@pytest.mark.parametrize("digest", [
    None,
    "",
    "7298d28c17d560ad4cc97906ab35ffbe2795130457f8374375ef529bcdc293ad",
    "sha1:504f587e140de5a907de40dc3c0b3a8419d3b026",
    "sha256:not-hex",
    "sha256:7298d28c",
])
def test_a_package_without_a_sha256_is_refused(answering, digest):
    """The algorithm is part of what is stated, and a fetch checking the wrong
    one would refuse every file it downloaded."""
    answering({**ANSWERED,
               "assets": [{**ANSWERED["assets"][0], "digest": digest}]})

    with pytest.raises(release.Unreachable):
        release.look()


def test_an_answer_that_is_not_json_is_not_an_answer(answering):
    answering(b"<html>a proxy said something else</html>")

    with pytest.raises(release.Unreachable):
        release.look()


def test_a_github_that_cannot_be_reached_is_said_so(answering):
    answering(OSError("no route to host"))

    with pytest.raises(release.Unreachable):
        release.look()


# -- what is kept, and what waits -----------------------------------------


def test_nothing_is_known_before_anything_is_asked(monkeypatch):
    """Which is the ordinary state of the first seconds after this service
    starts, and of a machine with no internet. Not an error, so not reported as
    one."""
    monkeypatch.setattr(release, "_look_behind_this", lambda: None)

    assert release.published() is None


def test_a_poll_reads_what_is_known_and_asks_for_nothing(monkeypatch):
    """The window redraws itself every two seconds while it is open. An address
    may ask GitHub sixty times an hour, so a poll that asked would spend that in
    twenty minutes and then stop answering without saying so."""
    monkeypatch.setattr(release, "_look_behind_this",
                        lambda: pytest.fail("asked anyway"))

    release.published()


def test_opening_the_window_asks(monkeypatch):
    """Which is the whole of what makes a release published while this runs
    turn up at all."""
    asked = []
    monkeypatch.setattr(release, "_look_behind_this",
                        lambda: asked.append(True))

    release.published(check=True)

    assert asked == [True]


def test_asking_happens_behind_the_answer(answering):
    """A reading that waited for GitHub would hold the window up for as long as
    a connection takes to fail, which on a board with no internet is the whole
    timeout."""
    answering(OSError("no route to host"))

    assert release.published(check=True) is None


def test_no_more_than_three_a_minute_leave_the_board(monkeypatch):
    """However often the window is opened. Three a minute sustained is already
    three times what an address is allowed an hour, and the floor is what stops
    somebody opening and closing it from going past even that."""
    asked = []
    monkeypatch.setattr(release, "look", lambda: asked.append(True))

    release.published(check=True)
    for _ in range(20):
        release.published(check=True)

    # The thread is started and finished before the next call, because `look`
    # here does nothing, so a second lookup would show up as a second entry.
    for _ in range(50):
        if asked:
            break
        time.sleep(0.02)

    assert asked == [True]


def test_the_floor_lets_go_once_it_has_passed(monkeypatch):
    """Twenty seconds later the window may ask again, which is what three a
    minute means."""
    asked = []
    monkeypatch.setattr(release, "_look_behind_this",
                        lambda: asked.append(True))

    release.published(check=True)
    release._ASKED_AT = time.time()
    release.published(check=True)
    release.published(check=True, now=time.time() + release.SOONEST_SECONDS)

    assert len(asked) == 2


def test_a_lookup_that_learns_nothing_still_counts_against_the_floor(monkeypatch):
    """The floor is about how often GitHub is asked rather than how often it
    answers. Counted the other way, a board whose network is down would ask
    again at every open with nothing holding it back."""
    def refuses():
        raise release.Unreachable("no route to host")

    monkeypatch.setattr(release, "look", refuses)

    release.published(check=True)
    for _ in range(50):
        if release._ASKED_AT:
            break
        time.sleep(0.02)

    assert release._ASKED_AT > 0


def test_what_is_answered_cannot_be_changed_from_outside(answering):
    """A dict handed out by reference is one a caller can edit, and the next
    reader would get the edit."""
    answering(ANSWERED)
    release.look()

    release.published()["version"] = "9.9.9"

    assert release.published()["version"] == "1.0.0"


def test_one_lookup_at_a_time(answering, monkeypatch):
    """A window polling every five seconds would otherwise start one per poll
    while the first is still waiting for a timeout."""
    holding = threading.Event()
    started = threading.Semaphore(0)

    def slowly():
        started.release()
        holding.wait(5)
        return dict(ANSWERED, asked_at=0.0)

    monkeypatch.setattr(release, "look", slowly)
    try:
        release._look_behind_this()
        assert started.acquire(timeout=5)
        release._look_behind_this()

        assert started.acquire(timeout=0.2) is False
    finally:
        holding.set()


def test_a_lookup_that_fails_leaves_the_reading_as_it_was(answering):
    """Nothing to do about it here, and the reading says so by staying absent."""
    answering(OSError("no route to host"))

    release._look_behind_this()

    assert release.published() is None


# -- every release, for its notes ------------------------------------------


#: What the list of every release holds, cut down to the fields this reads:
#: two releases, a draft, a prerelease, a tag that names no version, and
#: something that is not a release at all.
EVERY_ANSWERED = [
    {"tag_name": "v1.3.1", "body": "Two fixes."},
    {"tag_name": "v1.4.0", "draft": True, "body": "Not out yet."},
    {"tag_name": "v1.4.0-rc1", "prerelease": True, "body": "Trying it."},
    {"tag_name": "nightly", "body": "Whatever."},
    {"tag_name": "v1.3.0", "body": None},
    "not a release",
]


def test_every_published_release_is_read_newest_first(answering):
    """In the order GitHub lists them, which is newest first, and only the ones
    somebody could have installed: a draft is not out and a prerelease is not
    what an update brings."""
    answering(EVERY_ANSWERED)

    assert release.look_back() == [
        {"version": "1.3.1", "notes": "Two fixes."},
        {"version": "1.3.0", "notes": ""},
    ]


def test_a_list_that_is_not_a_list_is_no_answer(answering):
    answering({"message": "rate limited"})

    with pytest.raises(release.Unreachable):
        release.look_back()


def test_reading_the_list_asks_for_nothing(monkeypatch):
    """A window redrawing notes it already has does not cost a request."""
    monkeypatch.setattr(release, "_look_back_behind_this",
                        lambda: pytest.fail("asked anyway"))

    assert release.history() == []


def test_the_list_is_asked_for_while_it_is_out_of_date(monkeypatch):
    """Missing, or not holding the newest release there is. Once it holds that,
    the notes in it are what they will be until the next release."""
    asked = []
    monkeypatch.setattr(release, "_look_back_behind_this",
                        lambda: asked.append(True))
    later = time.time() + release.SOONEST_SECONDS

    release.history(check=True)
    release._HISTORY = [{"version": "1.3.1", "notes": "Two fixes."}]
    release._KNOWN = {"version": "1.3.1"}
    release.history(check=True, now=later)
    release._KNOWN = {"version": "1.3.2"}
    release.history(check=True, now=later)

    assert asked == [True, True]


def test_the_list_keeps_the_same_floor(monkeypatch):
    """However often notes are opened while it is out of date."""
    asked = []
    monkeypatch.setattr(release, "_look_back_behind_this",
                        lambda: asked.append(True))

    release.history(check=True)
    release._HISTORY_ASKED_AT = time.time()
    release.history(check=True)

    assert asked == [True]


def test_the_list_and_the_newest_are_asked_for_apart(answering):
    """The update reads the newest release alone, and a list that could not be
    read leaves it as it was."""
    answering(ANSWERED)
    release.look()
    answering(OSError("no route to host"))

    release._look_back_behind_this()
    for _ in range(50):
        if not release._LOOKING_BACK.locked():
            break
        time.sleep(0.02)

    assert release.history() == []
    assert release.published()["version"] == "1.0.0"


# -- what this is released from -------------------------------------------


@pytest.mark.parametrize("address", [release.NEWEST, release.EVERY])
def test_it_asks_about_this_repository_over_https(address):
    assert address.startswith("https://api.github.com/repos/")
    assert release.OWNER in address
    assert release.REPOSITORY in address


def test_the_hosts_are_the_three_a_download_actually_touches():
    """GitHub answers an asset download with a redirect to the host its release
    assets are served from, measured on 29 September 2026, so all three are
    needed and nothing else is."""
    assert set(release.HOSTS) == {"api.github.com", "github.com",
                                  "githubusercontent.com"}
