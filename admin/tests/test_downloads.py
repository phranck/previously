"""Downloads of the catalog's CD images into the owner's Software folder.

Nothing here reaches the network. The answer is handed in, and the download
runs where the test calls it rather than in a thread, so what is tested is what
is kept and what is refused.
"""

import hashlib
import io
import urllib.error

import pytest

from previously import downloads, software

#: What the image is in these tests: a few kilobytes, and its digest.
BODY = b"NeXT" * 4096
DIGEST = hashlib.sha1(BODY).hexdigest()


def an_entry(**changed):
    """@returns software.Entry, a CD image on archive.org that BODY is."""
    fields = dict(
        identifier="nextstep-3.3-developer",
        name="NeXTSTEP 3.3 Developer",
        description="",
        group="developer",
        version="3.3",
        systems=("nextstep-3.3",),
        address="https://archive.org/download/NeXTSTEP33CISC/NeXTSTEP_3.3_Developer.iso",
        size=len(BODY),
        algorithm="sha1",
        digest=DIGEST,
        kind="disc",
        cover="",
    )
    fields.update(changed)
    return software.Entry(**fields)


class Answering:
    """Stands in for the network: answers every address with one body, and
    keeps what was asked."""

    def __init__(self, body=BODY):
        self.body = body
        self.asked = []

    def __call__(self, url, hosts):
        self.asked.append((url, tuple(hosts)))
        return io.BytesIO(self.body)


def downloads_in(documents, answering=None, room=10 ** 9, begin=None):
    """@returns downloads.Downloads over a folder of the test's, which runs a
    download at once where no `begin` is given."""
    return downloads.Downloads(
        documents,
        open_address=answering or Answering(),
        room=lambda _path: room,
        begin=begin or (lambda work: work()))


def kept(documents):
    """@returns list of str, the names in the Software folder."""
    folder = documents / downloads.FOLDER
    return sorted(path.name for path in folder.iterdir()) if folder.exists() else []


def test_a_disc_lands_in_the_software_folder_under_its_identifier(tmp_path):
    loading = downloads_in(tmp_path)

    said = loading.start(an_entry())

    assert said["reason"] == "download.started"
    assert kept(tmp_path) == ["nextstep-3.3-developer.iso"]
    assert (tmp_path / "Software" / "nextstep-3.3-developer.iso").read_bytes() == BODY
    assert loading.state() == {"entry": "nextstep-3.3-developer", "done": len(BODY),
                               "of": len(BODY), "running": False,
                               "outcome": {"reason": "download.finished",
                                           "name": "NeXTSTEP 3.3 Developer"}}
    assert downloads.downloaded(tmp_path, an_entry()) == (
        tmp_path / "Software" / "nextstep-3.3-developer.iso")


def test_the_name_is_the_entry_s_whatever_the_address_says(tmp_path):
    """Never a name the address or the answer chose, so nothing from outside
    decides where a file lands."""
    downloads_in(tmp_path).start(
        an_entry(address="https://archive.org/download/x/..%2F..%2Fevil.cdr"))

    assert kept(tmp_path) == ["nextstep-3.3-developer.iso"]


def test_an_answer_of_the_wrong_size_is_not_kept(tmp_path):
    loading = downloads_in(tmp_path, Answering(BODY[:-1]))

    loading.start(an_entry())

    assert kept(tmp_path) == []
    assert loading.state()["outcome"]["reason"] == "download.wrong-size"


def test_an_answer_that_never_ends_stops_one_byte_past_the_entry(tmp_path):
    """Bounded while it is read, so an answer that runs on is not written to
    the card until it is full."""
    class Endless(io.RawIOBase):
        given = 0

        def read(self, size=-1):
            self.given += size
            return b"x" * size

    endless = Endless()
    loading = downloads_in(tmp_path, lambda url, hosts: endless)

    loading.start(an_entry())

    assert endless.given <= len(BODY) + 1
    assert kept(tmp_path) == []
    assert loading.state()["outcome"]["reason"] == "download.wrong-size"


def test_an_answer_with_the_wrong_digest_is_not_kept(tmp_path):
    loading = downloads_in(tmp_path, Answering(b"x" * len(BODY)))

    loading.start(an_entry())

    assert kept(tmp_path) == []
    assert loading.state()["outcome"]["reason"] == "download.wrong-digest"


def test_a_failed_request_says_so_and_keeps_nothing(tmp_path):
    def failing(url, hosts):
        raise urllib.error.URLError("no route to host")
    loading = downloads_in(tmp_path, failing)

    loading.start(an_entry())

    assert kept(tmp_path) == []
    assert loading.state()["outcome"]["reason"] == "download.failed"


def test_an_address_this_may_not_ask_is_said_as_such(tmp_path):
    """The address resolved into this network, or was redirected there."""
    def refusing(url, hosts):
        raise downloads.fetching.NotAllowed("not an address this may ask")
    loading = downloads_in(tmp_path, refusing)

    loading.start(an_entry())

    assert loading.state()["outcome"]["reason"] == "download.not-allowed"


@pytest.mark.parametrize("address, hosts", [
    # archive.org answers a download from one of its nodes.
    ("https://archive.org/download/x/x.iso", tuple(software.ARCHIVE_HOSTS)),
    # Anywhere else, the address's own host and nothing under or beside it.
    ("https://downloads.example.org/x.iso", ("downloads.example.org",)),
])
def test_a_download_may_reach_its_own_host(tmp_path, address, hosts):
    answering = Answering()

    downloads_in(tmp_path, answering).start(an_entry(address=address))

    assert answering.asked == [(address, hosts)]


@pytest.mark.parametrize("changed, reason", [
    ({"kind": "file"}, "download.not-a-disc"),
    ({"address": "http://archive.org/download/x/x.iso"}, "download.not-allowed"),
])
def test_what_cannot_be_downloaded_is_refused_before_anything_is_asked(
        tmp_path, changed, reason):
    loading = downloads_in(tmp_path, lambda url, hosts: pytest.fail("asked it anyway"))

    said = loading.start(an_entry(**changed))

    assert said["reason"] == reason
    assert kept(tmp_path) == []


def test_an_image_already_there_is_not_downloaded_again(tmp_path):
    loading = downloads_in(tmp_path)
    loading.start(an_entry())

    said = downloads_in(tmp_path, lambda url, hosts: pytest.fail("asked it anyway")).start(
        an_entry())

    assert said["reason"] == "download.already-there"


def test_one_download_runs_at_a_time(tmp_path):
    waiting = []
    loading = downloads_in(tmp_path, begin=waiting.append)
    loading.start(an_entry())

    said = loading.start(an_entry(identifier="another-one"))

    assert said == {"reason": "download.busy", "name": "NeXTSTEP 3.3 Developer"}
    assert loading.state()["running"] is True


def test_a_card_without_room_for_it_is_refused(tmp_path):
    said = downloads_in(tmp_path, room=len(BODY) - 1).start(an_entry())

    assert said["reason"] == "download.no-room"
    assert kept(tmp_path) == []


def test_what_an_interrupted_download_left_is_cleared_when_the_service_starts(tmp_path):
    """Only the service writes these, so one there at its start is from a run
    that ended with the service, and nothing will finish it."""
    folder = tmp_path / "Software"
    folder.mkdir()
    (folder / "nextstep-3.3-developer.iso.part").write_bytes(b"half")
    (folder / "kept.iso").write_bytes(b"whole")

    downloads_in(tmp_path)

    assert kept(tmp_path) == ["kept.iso"]


def test_nothing_downloaded_has_no_state(tmp_path):
    assert downloads_in(tmp_path).state() is None
