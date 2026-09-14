#!/usr/bin/env python3
"""Cut the machine out of a NeXT boot screen and make an icon of it.

While the boot ROM tests the hardware it puts up a panel: the NeXT cube on the
left, a line of text in the middle, and a picture of the machine on the right.
That picture is the only drawing of a NeXTcube and a NeXTstation the system
holds, and it is what the machines in the admin's shelf wear.

The input is a grab taken by Previous itself, which writes the emulated
framebuffer at 1120 by 832 in NeXT's four greys rather than the window as it
stands on the Pi's screen. Press Ctrl+Alt+G whilst the panel is up, and the
file appears in the emulator's working directory as next_screen_NNN.png.

    python3 bootpicture.py next_screen_021.png ../admin/web/parts/nextstation.png

Nothing here is measured against one particular screenshot: the panel is found
by its own grey and the picture by the gap that separates it from the text, so
the same call works for either machine.
"""

import sys

from PIL import Image

#: NeXT drew everything in these four greys and nothing between them.
PALETTE = [255, 170, 85, 0]

#: What the ROM paints its panel in, and therefore what surrounds the picture.
#: The desktop behind the panel is a different grey, which is what makes the
#: panel findable at all.
PANEL = 170

#: How far inside the panel to start looking. The panel carries a raised border
#: and a white rule a little way in, and both would otherwise read as part of
#: the picture.
MARGIN = 22

#: What an icon is drawn at in NeXTSTEP, and what the shelf expects.
ICON = 48


def panel_box(image):
    """Where the ROM's panel sits in the frame.

    @param image - The grab, as a greyscale Image.
    @returns (left, top, right, bottom), inclusive.
    @raises SystemExit - No panel grey in the frame, which means the grab was
      taken at a moment when the panel was not up.
    """
    pixels = image.load()
    left, top, right, bottom = image.width, image.height, -1, -1
    for y in range(image.height):
        for x in range(image.width):
            if pixels[x, y] == PANEL:
                left, top = min(left, x), min(top, y)
                right, bottom = max(right, x), max(bottom, y)
    if right < 0:
        raise SystemExit("no boot panel in this frame: nothing is panel grey")
    return left, top, right, bottom


def picture_box(image, panel):
    """Where the machine is drawn inside the panel.

    The panel holds the NeXT cube, the text and the machine, in that order and
    with clear space between them, so the machine is the last block of ink
    before the panel's right edge.

    @param image - The grab, as a greyscale Image.
    @param panel - What panel_box returned.
    @returns (left, top, right, bottom), inclusive.
    """
    pixels = image.load()
    left, top, right, bottom = panel
    inside = range(top + MARGIN, bottom - MARGIN + 1)

    inked = [x for x in range(left + MARGIN, right - MARGIN + 1)
             if any(pixels[x, y] != PANEL for y in inside)]
    if not inked:
        raise SystemExit("the panel is empty")

    # Walk back from the rightmost ink until the run breaks, which is the gap
    # between the text and the machine.
    last = inked[-1]
    first = last
    for column in reversed(inked):
        if first - column > 1:
            break
        first = column

    rows = [y for y in inside if any(pixels[x, y] != PANEL
                                     for x in range(first, last + 1))]
    return first, rows[0], last, rows[-1]


def to_icon(picture):
    """Reduces the picture to an icon with the panel grey taken out.

    @param picture - The cut-out machine, as a greyscale Image.
    @returns An RGBA Image of ICON by ICON.

    The reduction averages rather than picking nearest pixels, because the ROM
    draws its greys with dithering and picking would turn that into stripes.
    The result goes back onto the four greys afterwards, so the icon stays in
    the palette the rest of the interface is drawn in.
    """
    scale = ICON / max(picture.size)
    small = picture.resize((round(picture.width * scale),
                            round(picture.height * scale)), Image.BOX)
    small = small.point(lambda value: min(PALETTE, key=lambda step: abs(step - value)))

    # Flooding the panel grey inwards from the edges leaves the same grey
    # inside the machine opaque, which a plain colour key would not.
    alpha = Image.new("L", small.size, 255)
    seen = set()
    stack = [(x, y) for x in range(small.width) for y in (0, small.height - 1)]
    stack += [(x, y) for y in range(small.height) for x in (0, small.width - 1)]
    while stack:
        point = stack.pop()
        x, y = point
        if point in seen or not (0 <= x < small.width and 0 <= y < small.height):
            continue
        if small.getpixel(point) != PANEL:
            continue
        seen.add(point)
        alpha.putpixel(point, 0)
        stack += [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]

    icon = Image.new("LA", (ICON, ICON), (PANEL, 0))
    icon.paste(Image.merge("LA", (small, alpha)),
               ((ICON - small.width) // 2, (ICON - small.height) // 2))
    return icon.convert("RGBA")


def main(grab_path, out_path):
    image = Image.open(grab_path).convert("L")
    panel = panel_box(image)
    left, top, right, bottom = picture_box(image, panel)
    picture = image.crop((left, top, right + 1, bottom + 1))
    to_icon(picture).save(out_path)
    print("%s: panel %s, machine %d,%d to %d,%d (%d by %d) -> %s" % (
        grab_path, panel, left, top, right, bottom,
        picture.width, picture.height, out_path))


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: bootpicture.py <grab.png> <icon.png>")
    main(sys.argv[1], sys.argv[2])
