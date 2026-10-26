"""Which Previous the archive offers, read off its own index.

The index below is the stanza layout the archive served on 26 October 2026,
cut to the fields this reads, with the versions it listed.
"""

import gzip
import io
import urllib.error

import pytest

from previously import archive, setup

INDEX = """\
Package: previous
Version: 4.4-0wmlive1
Architecture: arm64

Package: previous
Version: 4.5-0wmlive1
Architecture: arm64

Package: wmaker
Version: 0.96.0-1wmlive1
Architecture: arm64

Package: previous
Version: 4.3-0wmlive1
Architecture: arm64
"""


def debian_order(version, other):
    """dpkg's ordering for the versions above, which differ only in the minor
    number, so a test runs on a machine without dpkg."""
    if not version or not other:
        return False
    return version.split("-")[0] < other.split("-")[0]


@pytest.fixture(autouse=True)
def without_dpkg(monkeypatch):
    monkeypatch.setattr(setup, "newer_than", debian_order)


@pytest.fixture
def serving(monkeypatch):
    """Makes the hosts answer what a test hands over, per address.

    @returns dict from address to the bytes it answers with, or an exception
      to raise instead. An address that is not in it cannot be reached.
    """
    answers = {}

    def opened(url, hosts, timeout, headers=None):
        said = answers.get(url, urllib.error.URLError("unreachable"))
        if isinstance(said, Exception):
            raise said
        return io.BytesIO(said)

    monkeypatch.setattr(archive.fetching, "opened", opened)
    return answers


def test_the_newest_version_is_chosen_wherever_it_stands():
    """The archive keeps every version it published, in no promised order."""
    assert archive.newest_in(INDEX, "previous") == "4.5-0wmlive1"


def test_a_package_the_index_does_not_list_is_none():
    assert archive.newest_in(INDEX, "nothing-of-the-kind") is None


def test_the_index_is_read_from_the_archive(serving):
    serving[archive.INDEXES[0]] = gzip.compress(INDEX.encode())

    assert archive.look()["version"] == "4.5-0wmlive1"


def test_the_copy_answers_where_the_archive_does_not(serving):
    serving[archive.INDEXES[1]] = gzip.compress(INDEX.encode())

    assert archive.look()["version"] == "4.5-0wmlive1"


def test_an_answer_that_is_not_an_index_is_no_answer(serving):
    serving[archive.INDEXES[0]] = b"<html>not found</html>"

    with pytest.raises(archive.Unreachable):
        archive.look()


def test_an_index_that_unpacks_past_any_real_one_is_refused(serving, monkeypatch):
    monkeypatch.setattr(archive, "LARGEST_UNPACKED", 64)
    serving[archive.INDEXES[0]] = gzip.compress(INDEX.encode())

    with pytest.raises(archive.Unreachable):
        archive.look()


def test_nothing_is_known_before_anything_is_asked(serving):
    assert archive.offered() is None


def test_a_reading_asks_for_nothing_unless_told_to(serving, monkeypatch):
    asked = []
    monkeypatch.setattr(archive, "look", lambda: asked.append(True))

    archive.offered()

    assert asked == []


def test_asking_keeps_a_floor_under_how_often(monkeypatch):
    started = []
    monkeypatch.setattr(archive, "_look_behind_this", lambda: started.append(True))
    monkeypatch.setattr(archive, "_ASKED_AT", 1000.0)

    archive.offered(check=True, now=1000.0 + archive.SOONEST_SECONDS - 1)
    archive.offered(check=True, now=1000.0 + archive.SOONEST_SECONDS)

    assert started == [True]


def test_it_asks_both_hosts_over_https_and_nothing_else():
    assert archive.INDEXES == (
        "https://wmlive.rumbero.org/repo/dists/wmlive-trixie/main/binary-arm64/Packages.gz",
        "https://previous.li/apt/wmlive/dists/wmlive-trixie/main/binary-arm64/Packages.gz",
    )
    assert archive.HOSTS == ("wmlive.rumbero.org", "previous.li")
