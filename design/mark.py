#!/usr/bin/env python3
"""Fetches the Previously mark and the pictures the Pi shows while it starts and
while it shuts down from the website, and writes the admin's copies.

The mark is drawn for the website at previous.li, by site/logo.py in
phranck/previous.li, and that is its one source. The admin shows it in the
About Previously panel and in the browser's tab, and this writes both copies
into admin/web/parts: Previously.png for the panel and favicon.ico for the tab.

The pictures the Pi shows while it starts and while it shuts down are drawn
there too, by site/splash.py out of the hero's board and trail, already at the
size and in the colours they are shown in. They go into admin/packaging, whose
build turns each into a TGA the package draws from, so they are copied as they
are. Run this again whenever the website's mark or those pictures change.

    python3 mark.py
"""

import io
import pathlib
import urllib.request

from PIL import Image

HERE = pathlib.Path(__file__).parent
PARTS = HERE.parent / "admin" / "web" / "parts"
#: Where the boot picture goes: beside the package build that turns it into a
#: TGA, because the admin's interface does not show it.
PACKAGING = HERE.parent / "admin" / "packaging"

#: Where the website keeps its files on main.
WEBSITE = "https://raw.githubusercontent.com/phranck/previous.li/main/site/"

#: The website's mark, and the icon its tab carries. The icon is the mark drawn
#: at 16, 32, 48 and 64 pixels, each size by site/logo.py on its own, so it is
#: copied as it is rather than scaled down here.
SOURCE = WEBSITE + "logo.png"
FAVICON = "favicon.ico"

#: The pictures shown while the Pi starts and while it shuts down. Already at
#: the size and in the colours they are shown in, so they are copied byte for
#: byte.
SPLASHES = ("splash.png", "splash-shutdown.png")

#: How tall the admin's copy is, in pixels: four times the 48 an icon is drawn
#: at, so it stays sharp on a display that doubles every pixel and on a desk
#: drawn at twice its size.
HEIGHT = 192


def downloaded(url):
    """@returns bytes, the file at that address."""
    with urllib.request.urlopen(url) as answer:
        return answer.read()


def fetched(url):
    """@returns Image, the picture at that address, in RGBA."""
    return Image.open(io.BytesIO(downloaded(url))).convert("RGBA")


def at_height(picture, height):
    """The picture scaled to a height, its width following in proportion.

    @param picture - Image.
    @param height - The height wanted, in pixels.
    @returns Image
    """
    width = round(picture.width * height / picture.height)
    return picture.resize((width, height), Image.LANCZOS)


def main():
    mark = at_height(fetched(SOURCE), HEIGHT)
    mark.save(PARTS / "Previously.png", optimize=True)
    (PARTS / FAVICON).write_bytes(downloaded(WEBSITE + FAVICON))
    for name in SPLASHES:
        (PACKAGING / name).write_bytes(downloaded(WEBSITE + name))
    print("wrote Previously.png at %d by %d and %s into %s, and %s into %s"
          % (mark.width, mark.height, FAVICON, PARTS, " and ".join(SPLASHES),
             PACKAGING))


if __name__ == "__main__":
    main()
