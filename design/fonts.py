#!/usr/bin/env python3
"""Fetches Ohlfs and writes the four faces the Terminal is set in.

Keith Ohlfs drew this face for NeXTSTEP as bitmaps, and Terminal.app was set in
its 12 pixel strike. jasonwoodland/ohlfs-font-extras decodes the original
Ohlfs.font bundle and writes each strike out as TrueType, with the Extra
variants carrying glyphs the original never had. This takes the four Screen 12
Extra faces from a commit named below, checks them against their sums, and
writes them into admin/web/fonts as WOFF2.

The two changes it makes on the way are in metrics rather than in outlines, and
line() says why each one is needed.

    python3 fonts.py
"""

import hashlib
import pathlib
import urllib.request

from fontTools.ttLib import TTFont

HERE = pathlib.Path(__file__).parent
SERVED = HERE.parent / "admin" / "web" / "fonts"

#: The commit the faces are taken from. A branch would make this script answer
#: differently on different days, and the sums below would then be the thing
#: that broke rather than the thing that checked.
UPSTREAM = "a937af36e051d2d713e560c9b6003af08d00e8ec"
SOURCE = ("https://raw.githubusercontent.com/jasonwoodland/ohlfs-font-extras/"
          + UPSTREAM + "/dist/ttf/%s.ttf")

#: What each file has to be. A face arriving over the network is a file from a
#: machine nobody here owns, and these are the four that were read and measured.
FACES = {
    "Ohlfs-Screen-12-Extra":
        "b2e0c194e10f53e207dc97e8e5e45885d003a8feeffdcc5a0349dfca9b525604",
    "Ohlfs-Screen-12-Extra-Bold":
        "cd9588595a399f94e514c16da083580367ea520edd1d48493c52f1237ad6dfc5",
    "Ohlfs-Screen-12-Extra-Italic":
        "8bee79cb7c1334a8a174d76eaf10a8267d5075ec41c203aa13d9a4582bab6bf5",
    "Ohlfs-Screen-12-Extra-Bold-Italic":
        "e5152f0d15d94ad7551a58d5acea33c5e417dd2a0fc2039e3e15715eb2f98589",
}

#: The line the face itself asks for, in font units, and the em it is drawn on.
#: Both are read off the upstream files: the ascent is 1300 units and the
#: descent 300, which is 16 px once the em of 1500 is set at 15 px.
ASCENT = 1300
DESCENT = 300


def fetch(name):
    """Downloads one face and checks it.

    @param name - The file's stem, such as "Ohlfs-Screen-12-Extra".
    @returns bytes of the TrueType file.
    @raises SystemExit where what arrived is not what was measured.
    """
    with urllib.request.urlopen(SOURCE % name) as answer:
        body = answer.read()
    got = hashlib.sha256(body).hexdigest()
    if got != FACES[name]:
        raise SystemExit("%s is not the file this was written against:\n"
                         "  expected %s\n  got      %s" % (name, FACES[name], got))
    return body


def line(font):
    """Makes every table say the same height, so every browser draws the same.

    A font carries its line in three places, and a browser picks one of them by
    platform rather than by anything the page can say. Ohlfs arrives with hhea
    and the typographic metrics both at 1300 over 300, which is the 16 px a
    line of the interface is, and with the Windows metrics at 1500 over 300,
    which is 18. A browser reading the third one would draw a terminal two
    pixels taller per row than the one beside it on the next machine.

    So all three are set to what the face itself says, and the flag that tells
    a browser to prefer the typographic pair is set with them. The outlines
    reach from 1300 down to -200, so nothing is cut by the smaller box.

    That flag lives in a field whose meaning arrived with version 4 of the
    table, and these faces carry version 3, where the same bit says nothing.
    Both versions hold the same fields, so the number is raised and no value
    moves.

    @param font - TTFont, changed in place.
    """
    hhea, os2 = font["hhea"], font["OS/2"]
    hhea.ascent, hhea.descent, hhea.lineGap = ASCENT, -DESCENT, 0
    os2.sTypoAscender, os2.sTypoDescender, os2.sTypoLineGap = ASCENT, -DESCENT, 0
    os2.usWinAscent, os2.usWinDescent = ASCENT, DESCENT
    os2.version = max(os2.version, 4)
    os2.fsSelection |= 1 << 7  # USE_TYPO_METRICS


def main():
    SERVED.mkdir(parents=True, exist_ok=True)
    written = 0
    for name in FACES:
        raw = HERE / (name + ".ttf")
        raw.write_bytes(fetch(name))
        font = TTFont(raw)
        line(font)
        # WOFF2, because these are served over a network to a browser and
        # nothing else ever opens them. The four come to a quarter of what the
        # TrueType files weigh.
        font.flavor = "woff2"
        font.save(SERVED / (name + ".woff2"))
        font.close()
        raw.unlink()
        written += 1
    print("wrote %d faces into %s" % (written, SERVED))


if __name__ == "__main__":
    main()
