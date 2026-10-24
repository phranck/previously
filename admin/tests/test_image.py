"""The OS list Raspberry Pi Imager reads the image from, held against what the
Imager asks of an entry and against the release that carries it.

Nothing here reaches the network: the image is a few bytes compressed the way
the real one is, and Raspberry Pi's own list is one written down here.
"""

import hashlib
import importlib.util
import lzma
import pathlib

import pytest

#: Where the image's own files live, beside the admin rather than inside it.
IMAGE = pathlib.Path(__file__).resolve().parent.parent.parent / "image"


@pytest.fixture(scope="module")
def os_list():
    """`image/os_list.py`, imported by path, as `build` is in test_packaging."""
    spec = importlib.util.spec_from_file_location("os_list", IMAGE / "os_list.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


#: What Raspberry Pi's own list says about the two boards and one more, as the
#: Imager reads them from its `imager.devices`.
OFFICIAL = {"imager": {"devices": [
    {"name": "Raspberry Pi 5", "tags": ["pi5-64bit", "pi5-32bit"]},
    {"name": "Raspberry Pi 4", "tags": ["pi4-64bit", "pi4-32bit"]},
    {"name": "Raspberry Pi 3", "tags": ["pi3-64bit", "pi3-32bit"]},
]}}


@pytest.fixture
def image(tmp_path):
    """A disk image of a few bytes, compressed with xz as the build does it.

    @returns (pathlib.Path, bytes): the compressed file and what it holds.
    """
    held = b"a disk image" * 1000
    path = tmp_path / "previously-raspberry-pi.img.xz"
    path.write_bytes(lzma.compress(held))
    return path, held


def test_an_entry_says_what_the_imager_checks_the_image_against(os_list, image):
    """The Imager checks what it wrote against the size and the digest of the
    image as it is unpacked, not as it was downloaded (rpi-imager
    doc/schema-notes.md)."""
    path, held = image

    entry, = os_list.listing(path, OFFICIAL, "2026-10-25")["os_list"]

    assert entry["extract_size"] == len(held)
    assert entry["extract_sha256"] == hashlib.sha256(held).hexdigest()
    assert entry["image_download_size"] == path.stat().st_size
    assert entry["release_date"] == "2026-10-25"


def test_an_entry_has_every_field_the_imager_requires(os_list, image):
    """The fields rpi-imager's schema notes list as required for an entry, and
    the customisation Raspberry Pi OS trixie itself is given, which is how the
    Imager sets the user, the hostname and the Wi-Fi."""
    entry, = os_list.listing(image[0], OFFICIAL, "2026-10-25")["os_list"]

    for field in ("name", "description", "icon", "url", "extract_size",
                  "extract_sha256", "image_download_size", "release_date",
                  "devices"):
        assert entry[field], field
    assert entry["init_format"] == "cloudinit-rpi"
    assert entry["devices"] == ["pi5-64bit", "pi4-64bit"]


def test_the_entry_points_at_the_image_of_its_own_release(os_list, image):
    """At the release that carries this list rather than at the newest one, so
    the digest in a list always belongs to the image it names."""
    from previously import server

    entry, = os_list.listing(image[0], OFFICIAL, "2026-10-25")["os_list"]

    assert entry["url"] == ("https://github.com/phranck/previously/releases/download/"
                            "v%s/%s" % (server.RELEASE, os_list.ASSET))


def test_the_list_carries_the_boards_the_image_is_for_and_no_others(os_list, image):
    """Taken from Raspberry Pi's own list by their tags, so the Imager shows
    them as it shows them for Raspberry Pi OS."""
    devices = os_list.listing(image[0], OFFICIAL, "2026-10-25")["imager"]["devices"]

    assert [device["name"] for device in devices] == ["Raspberry Pi 5", "Raspberry Pi 4"]


def test_the_release_attaches_the_image_and_its_list_under_these_names(os_list):
    """The release workflow names the files and the list names the image, so
    the two have to agree, and a link to releases/latest/download needs the
    same name in every release."""
    workflow = (IMAGE.parent / ".github" / "workflows" / "release.yml").read_text(
        encoding="utf-8")

    assert os_list.ASSET in workflow
    assert os_list.LIST in workflow
