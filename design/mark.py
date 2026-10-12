#!/usr/bin/env python3
"""Fetches the Previously mark from the website and writes the admin's copy.

The mark is drawn for the website at previous.li, by site/logo.py in
phranck/previous.li, and that is its one source. The admin shows it as the
application's icon, in the dock and in the About panel, and this writes that
copy into admin/web/parts/Previously.png. Run it again whenever the website's
mark changes.

    python3 mark.py
"""

import io
import pathlib
import urllib.request

from PIL import Image

HERE = pathlib.Path(__file__).parent
PARTS = HERE.parent / "admin" / "web" / "parts"

#: The website's mark, as main holds it.
SOURCE = "https://raw.githubusercontent.com/phranck/previous.li/main/site/logo.png"

#: How tall the admin's copy is, in pixels: four times the 48 an icon is drawn
#: at, so it stays sharp on a display that doubles every pixel and on a desk
#: drawn at twice its size.
HEIGHT = 192


def fetched(url):
    """@returns Image, the picture at that address, in RGBA."""
    with urllib.request.urlopen(url) as answer:
        return Image.open(io.BytesIO(answer.read())).convert("RGBA")


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
    print("wrote Previously.png at %d by %d into %s" % (mark.width, mark.height, PARTS))


if __name__ == "__main__":
    main()
