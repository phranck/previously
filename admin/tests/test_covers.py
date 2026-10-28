"""The covers the Pi keeps for software entries, fetched from archive.org once.

The pictures are the thumbnails archive.org made for NeXTSTEP33CISC and
nebula-se, recorded on 28 October 2026, so nothing here reaches the network.
"""

import pathlib
import urllib.error

from previously import covers, software

RECORDED = pathlib.Path(__file__).resolve().parent / "recorded"
FOLIO = (RECORDED / "archive-NeXTSTEP33CISC-folio_thumb.jpg").read_bytes()
PNG = b"\x89PNG\r\n\x1a\n" + b"\0" * 32
GIF = b"GIF89a" + b"\0" * 32


def an_entry(cover="https://archive.org/download/NeXTSTEP33CISC/NeXTSTEP%20CD%20Folio_thumb.jpg"):
    """@returns software.Entry, the shipped Developer CD with that cover."""
    return software.find("nextstep-3.3-developer")._replace(cover=cover)


def reading(body=FOLIO, error=None):
    """@returns A reader answering every address with `body`, or raising
    `error`, which counts how often it was asked."""
    def read(url):
        read.asked.append(url)
        if error is not None:
            raise error
        return body
    read.asked = []
    return read


def test_a_picture_is_known_by_its_first_bytes():
    assert covers.kind_of(FOLIO) == "image/jpeg"
    assert covers.kind_of(PNG) == "image/png"
    assert covers.kind_of(GIF) == "image/gif"
    assert covers.kind_of(b"<html>") is None
    assert covers.kind_of(b"") is None


def test_a_cover_is_fetched_once_and_kept(tmp_path):
    read = reading()

    first = covers.cover_of(tmp_path, an_entry(), read)
    second = covers.cover_of(tmp_path, an_entry(), read)

    assert first == second == (FOLIO, "image/jpeg")
    assert len(read.asked) == 1
    assert read.asked[0] == an_entry().cover


def test_another_cover_for_the_same_entry_replaces_the_one_kept(tmp_path):
    covers.cover_of(tmp_path, an_entry(), reading())
    other = an_entry(cover="https://archive.org/download/nebula-se/1neb%20%20front_thumb.jpg")

    assert covers.cover_of(tmp_path, other, reading(body=GIF)) == (GIF, "image/gif")
    assert len(list((tmp_path / covers.FOLDER).iterdir())) == 1


def test_what_is_no_picture_is_not_kept(tmp_path):
    assert covers.cover_of(tmp_path, an_entry(), reading(body=b"<html>moved</html>")) is None
    assert not (tmp_path / covers.FOLDER).exists() or not list((tmp_path / covers.FOLDER).iterdir())


def test_a_picture_past_the_ceiling_is_not_kept(tmp_path):
    large = FOLIO[:3] + b"\0" * covers.LARGEST_COVER

    assert covers.cover_of(tmp_path, an_entry(), reading(body=large)) is None


def test_archive_org_out_of_reach_is_no_cover_and_is_asked_again_later(tmp_path):
    read = reading(error=urllib.error.URLError("timed out"))

    assert covers.cover_of(tmp_path, an_entry(), read) is None
    assert covers.cover_of(tmp_path, an_entry(), reading()) == (FOLIO, "image/jpeg")


def test_an_entry_without_a_cover_asks_nobody(tmp_path):
    read = reading()

    assert covers.cover_of(tmp_path, an_entry(cover=""), read) is None
    assert read.asked == []


def test_forgetting_an_entry_takes_its_cover_away(tmp_path):
    covers.cover_of(tmp_path, an_entry(), reading())

    covers.forget(tmp_path, "nextstep-3.3-developer")

    assert not list((tmp_path / covers.FOLDER).iterdir())


def test_a_picture_becomes_an_address_the_page_can_show():
    assert covers.data_address(FOLIO).startswith("data:image/jpeg;base64,/9j/")
    assert covers.data_address(b"<html>") is None
