#!/usr/bin/env python3
"""Fetches Inconsolata and writes the two faces the Terminal is set in.

Inconsolata is a monospaced outline face under the SIL Open Font License, and
its release carries hinting, so it is drawn sharp at whatever size the desk is
drawn at. This takes the Regular and the Bold out of the release named below,
checks each against its sum, and writes them into admin/web/fonts as WOFF2,
with the license beside them.

The one change it makes on the way is in metrics rather than in outlines, and
line() says why it is needed.

    python3 fonts.py
"""

import hashlib
import io
import pathlib
import urllib.request
import zipfile

from fontTools.ttLib import TTFont

HERE = pathlib.Path(__file__).parent
SERVED = HERE.parent / "admin" / "web" / "fonts"

#: The release the faces are taken from. Its archive holds every width and
#: weight as a static file, and the static files are the ones that are hinted.
RELEASE = "https://github.com/googlefonts/Inconsolata/releases/download/v3.000/"
ARCHIVE = RELEASE + "fonts_ttf.zip"

#: What each file has to be. A face arriving over the network is a file from a
#: machine nobody here owns, and these are the two that were read and measured.
#: The sums are of the faces rather than of the archive, because the faces are
#: what is shipped.
FACES = {
    "Inconsolata-Regular":
        "127875d255d4c5973ca57267a43bb9d1c04397e6c7d236984a595b6cdcb12b7c",
    "Inconsolata-Bold":
        "263faa57f6c00c43a04e77df7abd5cb5cd4aae9f93507002c1217e02641fc7e6",
}

#: The license, which goes wherever the faces go: the OFL allows them to be
#: bundled with software on the condition that it travels with them.
LICENCE = "OFL.txt"
LICENCE_SUM = "5d362a6f8690517fd9a5573128a081d8bbbb2f92714cf00556e08fbbe9600426"

#: The line the faces are given, in font units on an em of 1000. One em, so
#: at the Terminal's 16 px a row is 16 px, the --line the rest of the
#: interface is built on. The descent is the face's own and the ascent is the
#: rest of the em.
ASCENT = 810
DESCENT = 190


def download(url, expected):
    """Downloads one file and checks it.

    @param url - Where it is.
    @param expected - Its SHA-256, as hex.
    @returns bytes of the file.
    @raises SystemExit where what arrived is not what was measured.
    """
    with urllib.request.urlopen(url) as answer:
        body = answer.read()
    checked(url, body, expected)
    return body


def checked(name, body, expected):
    """Holds one file to its sum.

    @param name - What to call it in the complaint.
    @param body - bytes of the file.
    @param expected - Its SHA-256, as hex.
    @raises SystemExit where the two differ.
    """
    got = hashlib.sha256(body).hexdigest()
    if got != expected:
        raise SystemExit("%s is not the file this was written against:\n"
                         "  expected %s\n  got      %s" % (name, expected, got))


def line(font):
    """Makes every table say the same height, so every browser draws the same.

    A font carries its line in three places, and a browser picks one of them by
    platform rather than by anything the page can say. Inconsolata arrives with
    hhea and the typographic metrics both at 859 over 190, which at the
    Terminal's 16 px is a line of 16.8, and with the Windows metrics at 1004
    over 454, which is 23.3. Neither is the 16 a row of this interface is, and
    the two of them disagree.

    So all three are set to ASCENT over DESCENT. Every character of ASCII stays
    inside that box, the tallest reaching 739 and the lowest -179. A few of
    Latin-1 pass it, the cedilla furthest at 15 units below, which is a
    quarter of a pixel and is drawn rather than cut.

    The release already sets the flag that tells a browser to prefer the
    typographic pair, in a table new enough to carry its meaning.

    @param font - TTFont, changed in place.
    """
    hhea, os2 = font["hhea"], font["OS/2"]
    hhea.ascent, hhea.descent, hhea.lineGap = ASCENT, -DESCENT, 0
    os2.sTypoAscender, os2.sTypoDescender, os2.sTypoLineGap = ASCENT, -DESCENT, 0
    os2.usWinAscent, os2.usWinDescent = ASCENT, DESCENT


def main():
    with urllib.request.urlopen(ARCHIVE) as answer:
        archive = zipfile.ZipFile(io.BytesIO(answer.read()))
    SERVED.mkdir(parents=True, exist_ok=True)
    for name, expected in FACES.items():
        body = archive.read("fonts/ttf/%s.ttf" % name)
        checked(name, body, expected)
        # The release's own date rather than today's, so a second run writes
        # the same bytes and git sees nothing to commit.
        font = TTFont(io.BytesIO(body), recalcTimestamp=False)
        line(font)
        # WOFF2, because these are served over a network to a browser and
        # nothing else ever opens them. It keeps the hinting, which is a table
        # like any other.
        font.flavor = "woff2"
        font.save(SERVED / (name + ".woff2"))
        font.close()
    (SERVED / LICENCE).write_bytes(download(RELEASE + LICENCE, LICENCE_SUM))
    print("wrote %d faces and their license into %s" % (len(FACES), SERVED))


if __name__ == "__main__":
    main()
