#!/usr/bin/env python3
"""Writes the OS list Raspberry Pi Imager reads Previously's image from.

    python3 image/os_list.py IMAGE --into os-list.json

The Imager customises an image, which is how it sets the user, the hostname
and the Wi-Fi, only where a list says how (rpi-imager
doc/os_customisation_formats.md), and it reads such a list when it is started
with `--repo <URL>`. The release attaches this one beside the image, so
`releases/latest/download/os-list.json` is always the newest.

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
import sys
import urllib.request

HERE = pathlib.Path(__file__).resolve().parent
PACKAGING = HERE.parent / "admin" / "packaging"

#: What the release attaches the image and the list as, the same in every
#: release, so an address under releases/latest/download is always the newest.
ASSET = "previously-raspberry-pi.img.xz"
LIST = "os-list.json"

#: Where an image of a given release is, by its tag and the asset's name.
RELEASE_ASSET = "https://github.com/phranck/previously/releases/download/v%s/%s"

#: The picture the Imager shows beside the entry, which previous.li serves.
ICON = "https://previous.li/site/icon-192.png"

#: The boards the image starts on, by the tags Raspberry Pi's own list gives
#: them, and the customisation Raspberry Pi OS trixie is given there, which the
#: image keeps because it is Raspberry Pi OS Lite underneath.
DEVICES = ["pi5-64bit", "pi4-64bit"]
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
    @returns dict, what goes into LIST.
    """
    size, digest = unpacked(image)
    version = release()
    devices = [device for device in official["imager"]["devices"]
               if set(device.get("tags", ())) & set(DEVICES)]
    return {
        "imager": {"devices": devices},
        "os_list": [{
            "name": "Previously",
            "description": "Raspberry Pi OS Lite with Previously %s and NeXTSTEP 3.3"
                           % version,
            "icon": ICON,
            "url": RELEASE_ASSET % (version, ASSET),
            "extract_size": size,
            "extract_sha256": digest,
            "image_download_size": image.stat().st_size,
            "release_date": date,
            "init_format": INIT_FORMAT,
            "devices": DEVICES,
        }],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("image", type=pathlib.Path, help="the .img.xz the release carries")
    parser.add_argument("--into", type=pathlib.Path, required=True,
                        help="where to write the list")
    arguments = parser.parse_args()

    with urllib.request.urlopen(OFFICIAL, timeout=60) as answer:
        official = json.load(answer)
    written = listing(arguments.image, official,
                      datetime.datetime.now(datetime.timezone.utc).date().isoformat())
    arguments.into.write_text(json.dumps(written, indent=2) + "\n", encoding="utf-8")
    print("wrote %s" % arguments.into)


if __name__ == "__main__":
    sys.exit(main())
