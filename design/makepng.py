#!/usr/bin/env python3
"""Draws the icon a PNG wears, in the way NeXT drew the ones for its own
picture formats.

NeXTSTEP had no generic icon for a picture. What it had was one per format,
each a white sheet carrying the format's name in a serif face across the top
and a picture of the kind of content underneath: a raster gradient on
tiff.tiff, a bezier curve on eps.tiff. There was no PNG in 1993, so there is
nothing to extract and this draws one in the same manner.

The sheet, its shadow and the gradient are tiff.tiff's own, so the only thing
made up here is the lettering. Times Bold at seventeen is what comes closest
to the face NeXT set TIFF in, and the ink is the blue that picture's letters
are mostly made of.

    python3 makepng.py
"""

import pathlib

from PIL import Image, ImageDraw, ImageFont

HERE = pathlib.Path(__file__).parent
PARTS = HERE / "parts"

#: What the lettering is set in. Measured against tiff.tiff: mostly pure blue
#: with darker blues where the strokes thicken.
INK = (0, 0, 220, 255)
FACE = "/System/Library/Fonts/Supplemental/Times New Roman Bold.ttf"
SIZE = 17

#: Where TIFF stands on that sheet, which is where PNG goes: rows 4 to 18 of a
#: 48 square icon, inside the sheet's own white.
LETTERING = [3, 4, 44, 18]
MIDDLE = (24, 11)


def main():
    sheet = Image.open(PARTS / "tiff.png").convert("RGBA")
    draw = ImageDraw.Draw(sheet)
    draw.rectangle(LETTERING, fill=(255, 255, 255, 255))

    font = ImageFont.truetype(FACE, SIZE)
    left, top, right, bottom = draw.textbbox((0, 0), "PNG", font=font)
    draw.text((MIDDLE[0] - (right - left) / 2 - left,
               MIDDLE[1] - (bottom - top) / 2 - top),
              "PNG", font=font, fill=INK)

    sheet.save(PARTS / "png.png")
    print("wrote parts/png.png")


if __name__ == "__main__":
    main()
