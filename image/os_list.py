#!/usr/bin/env python3
"""Writes the OS list Raspberry Pi Imager reads Previously's image from, and
the picture of each board beside it.

    python3 image/os_list.py IMAGE --into DIRECTORY

The Imager customises an image, which is how it sets the user, the hostname
and the Wi-Fi, only where a list says how (rpi-imager
doc/os_customisation_formats.md), and it reads such a list when it is started
with `--repo <URL>`. The release attaches this one beside the image, so
`releases/latest/download/os-list.json` is always the newest.

The list has an entry for each board, both for the same image. The Imager
shows only the entries whose devices carry a tag of the board chosen a step
before, so each board appears with its own drawing, the one the admin shows
for it.

The list names the image of its own release rather than the newest one, so the
digest it carries always belongs to the image it names. Which release that is
comes from `packaging/build.py`, which reads it out of the service.
"""

import argparse
import datetime
import hashlib
import importlib.util
import json
import lzma
import pathlib
import re
import subprocess
import sys
import urllib.request

HERE = pathlib.Path(__file__).resolve().parent
ADMIN = HERE.parent / "admin"
PACKAGING = ADMIN / "packaging"

#: Where the admin keeps its drawing of each board, as `board-<name>.svg`.
PARTS = ADMIN / "web" / "parts"

#: What the release attaches the image and the list as, the same in every
#: release, so an address under releases/latest/download is always the newest.
#: Each board's picture goes beside them as ICON.
ASSET = "previously-raspberry-pi.img.xz"
LIST = "os-list.json"
ICON = "previously-%s.png"

#: Where a file of a given release is, by its tag and the file's name.
RELEASE_ASSET = "https://github.com/phranck/previously/releases/download/v%s/%s"

#: The boards the image starts on, by the tag Raspberry Pi's own list gives
#: each, and the name of its drawing among PARTS. In the order the Imager
#: lists them.
BOARDS = {"pi5-64bit": "pi5", "pi4-64bit": "pi4"}

#: How many pixels a side a picture is: the drawing at twice its width, so
#: its pixels stay square, in a square like the Imager's own pictures.
ICON_SIDE = 144

#: The customisation Raspberry Pi OS trixie is given in Raspberry Pi's own
#: list, which the image keeps because it is Raspberry Pi OS Lite underneath.
INIT_FORMAT = "cloudinit-rpi"

#: Raspberry Pi's own list, which the Imager reads when nothing else is named.
#: The boards are taken from there, so the Imager shows them as it shows them
#: for Raspberry Pi OS.
OFFICIAL = "https://downloads.raspberrypi.com/os_list_imagingutility_v4.json"

#: How much of the image to unpack at a time while it is measured.
CHUNK_BYTES = 4 * 1024 * 1024


def release():
    """@returns str, the release this tree is, as `packaging/build.py` reads
    it out of the service."""
    spec = importlib.util.spec_from_file_location("build", PACKAGING / "build.py")
    build = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(build)
    return build.release()


def unpacked(image):
    """What the image is once the Imager has unpacked it.

    @param image - pathlib.Path of the .img.xz.
    @returns (int, str): its size in bytes and its SHA-256 as hex, which is
      what the Imager checks what it wrote against.
    """
    digest = hashlib.sha256()
    size = 0
    with lzma.open(image) as reading:
        while True:
            chunk = reading.read(CHUNK_BYTES)
            if not chunk:
                break
            digest.update(chunk)
            size += len(chunk)
    return size, digest.hexdigest()


def listing(image, official, date):
    """The OS list for one image.

    @param image - pathlib.Path of the .img.xz.
    @param official - Raspberry Pi's own list, as JSON reads it.
    @param date - str, the release date as YYYY-MM-DD.
    @returns dict, what goes into LIST: an entry for each of BOARDS, and those
      boards as Raspberry Pi's own list describes them.
    """
    size, digest = unpacked(image)
    version = release()
    devices = [device for device in official["imager"]["devices"]
               if set(device.get("tags", ())) & set(BOARDS)]
    return {
        "imager": {"devices": devices},
        "os_list": [{
            "name": "Previously",
            "description": "Raspberry Pi OS Lite with Previously %s and NeXTSTEP 3.3"
                           % version,
            "icon": RELEASE_ASSET % (version, ICON % board),
            "url": RELEASE_ASSET % (version, ASSET),
            "extract_size": size,
            "extract_sha256": digest,
            "image_download_size": image.stat().st_size,
            "release_date": date,
            "init_format": INIT_FORMAT,
            "devices": [tag],
        } for tag, board in BOARDS.items()],
    }


def squared(drawing):
    """A board's drawing in a square of ICON_SIDE pixels.

    @param drawing - str, the SVG as PARTS holds it.
    @returns str, the same SVG with only the size on its root changed. The
      viewBox stays, and SVG fits a viewBox into a box of another shape whole
      and in the middle unless told otherwise, so the drawing keeps its
      proportions with room above and below.
    """
    root = re.search(r"<svg[^>]*>", drawing).group(0)
    sized = re.sub(r'\bwidth="[^"]*"', 'width="%d"' % ICON_SIDE, root, count=1)
    sized = re.sub(r'\bheight="[^"]*"', 'height="%d"' % ICON_SIDE, sized, count=1)
    return drawing.replace(root, sized, 1)


def rendered(drawing, into):
    """Writes a squared drawing as a PNG, with rsvg-convert.

    @param drawing - pathlib.Path of the SVG.
    @param into - pathlib.Path of the PNG.
    """
    subprocess.run(["rsvg-convert", "--format", "png", "--output", str(into)],
                   input=squared(drawing.read_text(encoding="utf-8")).encode("utf-8"),
                   check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("image", type=pathlib.Path, help="the .img.xz the release carries")
    parser.add_argument("--into", type=pathlib.Path, required=True,
                        help="the directory to write the list and the pictures into")
    arguments = parser.parse_args()
    arguments.into.mkdir(parents=True, exist_ok=True)

    with urllib.request.urlopen(OFFICIAL, timeout=60) as answer:
        official = json.load(answer)
    written = listing(arguments.image, official,
                      datetime.datetime.now(datetime.timezone.utc).date().isoformat())
    (arguments.into / LIST).write_text(json.dumps(written, indent=2) + "\n",
                                       encoding="utf-8")
    for board in BOARDS.values():
        rendered(PARTS / ("board-%s.svg" % board), arguments.into / (ICON % board))
    print("wrote %s and %d pictures into %s" % (LIST, len(BOARDS), arguments.into))


if __name__ == "__main__":
    sys.exit(main())
