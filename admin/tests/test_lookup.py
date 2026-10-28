"""Filling in a software entry from an archive.org address.

Every test reads the answer archive.org gave for NeXTSTEP33CISC on 27 October
2026, kept whole in `recorded/archive-NeXTSTEP33CISC.json`, so nothing here
reaches the network and what is read is what archive.org actually says.
"""

import json
import pathlib
import urllib.error

import pytest

from previously import lookup, software

RECORDED = pathlib.Path(__file__).resolve().parent / "recorded" / "archive-NeXTSTEP33CISC.json"
DEVELOPER = "https://archive.org/download/NeXTSTEP33CISC/NeXTSTEP_3.3_Developer.iso"


def answering(body=None, error=None):
    """@returns A reader as `lookup.look_up` takes one, which answers every
    address with `body`, the recorded answer where none is given, or raises
    `error`, and keeps what it was asked."""
    asked = []

    def read(url):
        asked.append(url)
        if error is not None:
            raise error
        return RECORDED.read_bytes() if body is None else body

    read.asked = asked
    return read


def test_an_address_naming_a_file_fills_in_what_archive_org_says_about_it():
    read = answering()

    ok, said = lookup.look_up(DEVELOPER, read)

    assert ok, said
    assert said["reason"] == "lookup.found"
    fields = said["fields"]
    assert fields["name"] == "NeXTSTEP 3.3 Developer"
    assert fields["address"] == DEVELOPER
    assert fields["size"] == 403111936
    assert fields["algorithm"] == "sha1"
    assert fields["digest"] == "268c66059c3c48df3bb4d2498785f2459bfa73cd"
    assert fields["kind"] == "disc"
    # Asked of the item's metadata and of the thumbnail of its cover, both on
    # archive.org, and of nothing else.
    assert read.asked == ["https://archive.org/metadata/NeXTSTEP33CISC", FOLIO]


def test_the_description_is_plain_text():
    """archive.org keeps HTML in it, and a field shows text."""
    _, said = lookup.look_up(DEVELOPER, answering())
    description = said["fields"]["description"]

    assert description.startswith("This is the CD-ROM images of NeXTSTEP 3.3")
    assert "<" not in description and "\xa0" not in description
    assert len(description) <= software.LONGEST_DESCRIPTION


def test_a_line_break_in_the_description_stays_a_space_between_words():
    """archive.org writes `nebula-se`'s description in lines parted by <br>,
    and the words either side of one are two words."""
    text = lookup.plain_text(
        "Nebula Second Edition<br>June 1994<br/>Version 2.0<p>Thank you</p>", 500)

    assert text == "Nebula Second Edition June 1994 Version 2.0 Thank you"


def test_what_is_filled_in_passes_the_catalog_s_own_rules():
    """The fields the window gets are the ones a save checks, so whatever the
    adapter fills in is something the catalog takes."""
    _, said = lookup.look_up(DEVELOPER, archive())
    entry = software.Entry(identifier="x", group="developer", version="3.3",
                           systems=("nextstep-3.3",), **said["fields"])

    assert software.problems(entry) == []


def test_an_address_naming_an_item_offers_the_files_worth_having():
    """Metadata, a torrent and the thumbnails are archive.org's own, and are
    not what anybody came for."""
    ok, said = lookup.look_up("https://archive.org/details/NeXTSTEP33CISC", answering())

    assert ok
    assert said["reason"] == "lookup.choose"
    names = [one["name"] for one in said["files"]]
    assert "NeXTSTEP_3.3_Developer.iso" in names
    assert "3.3_Boot_Disk.img" in names
    assert not [name for name in names if name.endswith((".xml", ".torrent", ".sqlite"))
                or "thumb" in name]
    developer = next(one for one in said["files"] if one["name"] == "NeXTSTEP_3.3_Developer.iso")
    assert developer == {"name": "NeXTSTEP_3.3_Developer.iso", "size": 403111936,
                         "kind": "disc", "address": DEVELOPER}


def test_a_floppy_image_is_not_taken_for_a_cd():
    """archive.org calls a 1.44 MB disk image an ISO Image as well."""
    _, said = lookup.look_up(
        "https://archive.org/download/NeXTSTEP33CISC/3.3_Boot_Disk.img", answering())

    assert said["fields"]["kind"] == "file"


def test_a_file_name_with_spaces_and_brackets_is_found_and_written_as_an_address():
    _, said = lookup.look_up(
        "https://archive.org/download/NeXTSTEP33CISC/NeXTSTEP_3.3_User_%28i386_m68k%29.iso",
        answering())

    assert said["fields"]["name"] == "NeXTSTEP 3.3 User (i386 m68k)"
    assert said["fields"]["address"] == (
        "https://archive.org/download/NeXTSTEP33CISC/NeXTSTEP_3.3_User_%28i386_m68k%29.iso")


@pytest.mark.parametrize("address, reason", [
    (DEVELOPER.replace("https:", "http:"), "lookup.not-an-address"),
    ("archive.org/download/NeXTSTEP33CISC", "lookup.not-an-address"),
    ("https://archive.org/" + "x" * 2048, "lookup.not-an-address"),
    (42, "lookup.not-an-address"),
    ("https://example.org/download/NeXTSTEP33CISC/x.iso", "lookup.no-adapter"),
    ("https://archive.org.example.com/download/NeXTSTEP33CISC/x.iso", "lookup.no-adapter"),
    ("https://archive.org/about", "lookup.not-an-item"),
    ("https://archive.org/download/../etc/passwd", "lookup.not-an-item"),
    ("https://archive.org/download/NeXTSTEP33CISC/nothing.iso", "lookup.no-such-file"),
])
def test_an_address_this_cannot_read_is_refused_by_name(address, reason):
    ok, said = lookup.look_up(address, answering())

    assert not ok
    assert said["reason"] == reason


def test_a_refused_address_asks_nobody():
    read = answering()

    lookup.look_up("https://example.org/download/NeXTSTEP33CISC/x.iso", read)

    assert read.asked == []


def test_an_item_archive_org_does_not_have_is_said_as_such():
    """archive.org answers an item it does not hold with an empty object."""
    ok, said = lookup.look_up("https://archive.org/details/nothing-here", answering(b"{}"))

    assert (ok, said) == (False, {"reason": "lookup.no-such-item", "item": "nothing-here"})


def test_archive_org_out_of_reach_is_said_as_such():
    ok, said = lookup.look_up(DEVELOPER, answering(error=urllib.error.URLError("timed out")))

    assert not ok
    assert said["reason"] == "lookup.unreachable"


def test_an_answer_that_is_not_what_archive_org_sends_is_said_as_such():
    ok, said = lookup.look_up(DEVELOPER, answering(b"<html>not json</html>"))

    assert (ok, said) == (False, {"reason": "lookup.unreadable"})


def test_a_value_that_breaks_its_rule_is_left_out_rather_than_filled_in():
    """What arrives is a third party's, so a size that is no number and a
    digest that is no digest leave their fields to whoever adds the entry."""
    answer = json.loads(RECORDED.read_bytes())
    developer = next(one for one in answer["files"] if one["name"] == "NeXTSTEP_3.3_Developer.iso")
    # A digit to str.isdigit and not to int.
    developer["size"] = "²"
    developer["sha1"] = "<script>"

    ok, said = lookup.look_up(DEVELOPER, answering(json.dumps(answer).encode()))

    assert ok
    assert "size" not in said["fields"]
    assert "digest" not in said["fields"]
    assert said["fields"]["name"] == "NeXTSTEP 3.3 Developer"


RECORDED_DIR = RECORDED.parent
FOLIO = "https://archive.org/download/NeXTSTEP33CISC/NeXTSTEP%20CD%20Folio_thumb.jpg"
NEBULA_FRONT = "https://archive.org/download/nebula-se/1neb%20%20front_thumb.jpg"


def archive(**changed):
    """@returns A reader that answers as archive.org did on 27 and 28 October
    2026: the metadata of both items and the two thumbnails, with what is
    given in `changed` answered instead, by address."""
    answers = {
        "https://archive.org/metadata/NeXTSTEP33CISC": RECORDED.read_bytes(),
        "https://archive.org/metadata/nebula-se":
            (RECORDED_DIR / "archive-nebula-se.json").read_bytes(),
        FOLIO: (RECORDED_DIR / "archive-NeXTSTEP33CISC-folio_thumb.jpg").read_bytes(),
        NEBULA_FRONT: (RECORDED_DIR / "archive-nebula-se-front_thumb.jpg").read_bytes(),
    }
    answers.update(changed)

    def read(url):
        if url not in answers:
            raise urllib.error.URLError("nothing recorded for " + url)
        return answers[url]
    return read


def test_the_cover_is_the_thumbnail_of_the_item_s_folio_where_it_has_no_front():
    ok, said = lookup.look_up(DEVELOPER, archive())

    assert ok
    assert said["fields"]["cover"] == FOLIO
    # The thumbnail itself rides along, so the window can show it before the
    # entry is kept and the Pi can hand it out.
    assert said["picture"].startswith("data:image/jpeg;base64,/9j/")


def test_the_front_wins_over_the_back_and_the_disc():
    _, said = lookup.look_up("https://archive.org/download/nebula-se/NEBULA_SE.ISO", archive())

    assert said["fields"]["cover"] == NEBULA_FRONT


def test_a_thumbnail_that_is_no_picture_is_no_cover():
    _, said = lookup.look_up(DEVELOPER, archive(**{FOLIO: b"<html>moved</html>"}))

    assert "cover" not in said["fields"]
    assert "picture" not in said


def test_a_thumbnail_out_of_reach_leaves_the_entry_without_a_cover():
    read = archive()

    def unreachable(url):
        if url == FOLIO:
            raise urllib.error.URLError("timed out")
        return read(url)

    ok, said = lookup.look_up(DEVELOPER, unreachable)

    assert ok
    assert "cover" not in said["fields"]


def test_an_item_without_pictures_has_no_cover():
    answer = json.loads(RECORDED.read_bytes())
    answer["files"] = [one for one in answer["files"] if one.get("format") != "JPEG"
                       and one.get("format") != "JPEG Thumb"]
    ok, said = lookup.look_up(DEVELOPER, answering(json.dumps(answer).encode()))

    assert ok
    assert "cover" not in said["fields"]
