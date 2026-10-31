#!/usr/bin/env python3
"""Fetches the faces the admin sets its text in, and writes them where it serves them.

Two families, each taken out of its release, checked against its sum and
written into admin/web/fonts with its license beside it:

TeX Gyre Heros, Regular and Bold, which the interface is set in. It goes
there as the release's OpenType files, unchanged.

Inconsolata, Regular and Bold, which code and the Terminal are set in. It is
a monospaced outline face under the SIL Open Font License, and its release
carries hinting, so it is drawn sharp at whatever size the desk is drawn at.
It goes there as WOFF2, with one change in metrics rather than in outlines,
and line() says why that change is needed.

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

#: TeX Gyre Heros's 2.004 release as GUST, who make it, publish it: one archive
#: holding the OpenType files of every weight and width.
HEROS_ARCHIVE = "https://www.gust.org.pl/projects/e-foundry/tex-gyre/heros/qhv2.004otf.zip"

#: Where a face of it stands in that archive, by the face's name.
HEROS_MEMBER = "%s.otf"

#: The two faces of it the interface sets text in, by their names in the
#: release, and what each file has to be. A face arriving over the network is
#: a file from a machine nobody here owns, and these are the ones that were
#: read and measured. The sums are of the faces rather than of the archive,
#: because the faces are what is shipped.
HEROS_FACES = {
    "texgyreheros-regular":
        "6ae1a09d5a940367b7aaaa91ee8bd8a2c333bfe193e7096e23f931357d62081f",
    "texgyreheros-bold":
        "b170162835f4efc288886dd4231406dc47e19b614cf4416836635599d44a7d60",
}

#: Its license, which goes beside the faces, and where GUST publishes it.
HEROS_LICENSE = "GUST-FONT-LICENSE.txt"
HEROS_LICENSE_URL = "https://www.gust.org.pl/projects/e-foundry/licenses/" + HEROS_LICENSE
HEROS_LICENSE_SUM = "5eb61bb836bb1845ef668717cb15b382e997748ce2629e4388cc5e4c3fa4e433"

#: The Inconsolata release the faces are taken from. Its archive holds every
#: width and weight as a static file, and the static files are the ones that
#: are hinted.
INCONSOLATA_RELEASE = "https://github.com/googlefonts/Inconsolata/releases/download/v3.000/"
INCONSOLATA_ARCHIVE = INCONSOLATA_RELEASE + "fonts_ttf.zip"

#: Where a face of it stands in that archive, by the face's name.
INCONSOLATA_MEMBER = "fonts/ttf/%s.ttf"

#: What each file has to be, for the same reason as TeX Gyre Heros's.
INCONSOLATA_FACES = {
    "Inconsolata-Regular":
        "127875d255d4c5973ca57267a43bb9d1c04397e6c7d236984a595b6cdcb12b7c",
    "Inconsolata-Bold":
        "263faa57f6c00c43a04e77df7abd5cb5cd4aae9f93507002c1217e02641fc7e6",
}

#: The license, which goes wherever the faces go: the OFL allows them to be
#: bundled with software on the condition that it travels with them.
INCONSOLATA_LICENSE = "OFL.txt"
INCONSOLATA_LICENSE_SUM = "5d362a6f8690517fd9a5573128a081d8bbbb2f92714cf00556e08fbbe9600426"

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


def faces_in(url, member, faces):
    """Takes faces out of a release's archive, each held to its sum.

    @param url - Where the archive is. It is not checked itself, because what
        is shipped is the faces in it, and each of those is.
    @param member - Where a face stands in the archive, with %s for its name.
    @param faces - dict of each face's name to its SHA-256, as hex.
    @returns list of (name, bytes of the face), in the order of faces.
    @raises SystemExit where a face is not the file that was measured.
    """
    with urllib.request.urlopen(url) as answer:
        archive = zipfile.ZipFile(io.BytesIO(answer.read()))
    taken = []
    for name, expected in faces.items():
        body = archive.read(member % name)
        checked(name, body, expected)
        taken.append((name, body))
    return taken


def main():
    SERVED.mkdir(parents=True, exist_ok=True)

    for name, body in faces_in(HEROS_ARCHIVE, HEROS_MEMBER, HEROS_FACES):
        # Unchanged. In each face the hhea and the Windows metrics already
        # agree, and neither asks a browser for the typographic pair, so every
        # browser reads the same line from it, which is what line() has to
        # make Inconsolata do. OpenType rather than WOFF2, because a menu
        # drawn outside a browser takes its glyphs from these same files, and
        # a browser reads either. Under its name in the release, so the file
        # served is recognizably the file published.
        (SERVED / (HEROS_MEMBER % name)).write_bytes(body)
    (SERVED / HEROS_LICENSE).write_bytes(download(HEROS_LICENSE_URL, HEROS_LICENSE_SUM))

    for name, body in faces_in(INCONSOLATA_ARCHIVE, INCONSOLATA_MEMBER, INCONSOLATA_FACES):
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
    (SERVED / INCONSOLATA_LICENSE).write_bytes(
        download(INCONSOLATA_RELEASE + INCONSOLATA_LICENSE, INCONSOLATA_LICENSE_SUM))

    print("wrote %d faces and their licenses into %s"
          % (len(HEROS_FACES) + len(INCONSOLATA_FACES), SERVED))


if __name__ == "__main__":
    main()
