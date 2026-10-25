#!/usr/bin/env python3
"""Reads a frame buffer grab of Previous and says where the picture is.

A grab is the emulated frame buffer as Previous's own Ctrl+Alt+G writes it,
1120 by 832 in NeXT's four grays. The question the experiment asks is which
part of that buffer the guest draws into, so the script reports, for the whole
picture and for a band of rows, how the gray levels are distributed and where
the content starts and ends. Numbers, not an impression.

    measure_grab.py <grab.png> [--band <first>:<last>]...

The band is given as first and last row, both inclusive. Without a band the
picture is reported as one.
"""

import argparse
from collections import Counter

from PIL import Image

NEXT_GRAYS = {0: "black", 85: "dark", 170: "light", 255: "white"}


def gray_name(level):
    """@returns str - NeXT's name for a gray level, or the level itself."""
    return NEXT_GRAYS.get(level, str(level))


def report_band(pixels, width, first_row, last_row):
    """Prints the gray histogram and the content bounds of the rows first_row to last_row."""
    rows = range(first_row, last_row + 1)
    histogram = Counter()
    for row in rows:
        histogram.update(pixels[row * width:(row + 1) * width])
    total = sum(histogram.values())
    background = histogram.most_common(1)[0][0]
    print("rows %d to %d: background %s" % (first_row, last_row, gray_name(background)))
    for level, count in sorted(histogram.items()):
        print("    %-6s %6.2f%%" % (gray_name(level), 100.0 * count / total))

    content_rows = [row for row in rows if any(value != background for value in pixels[row * width:(row + 1) * width])]
    if not content_rows:
        print("    no content, the band is uniform")
        return
    columns_with_content = set()
    for row in content_rows:
        line = pixels[row * width:(row + 1) * width]
        columns_with_content.update(column for column, value in enumerate(line) if value != background)
    print("    content rows %d to %d, columns %d to %d" % (
        content_rows[0], content_rows[-1], min(columns_with_content), max(columns_with_content)))
    last_rows = [row for row in content_rows if row >= last_row - 100]
    print("    rows with content in the last 100 of the band: %d" % len(last_rows))


def main():
    """Parses the command line and reports every band asked for."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("grab")
    parser.add_argument("--band", action="append", default=[], help="first:last rows, inclusive")
    arguments = parser.parse_args()

    image = Image.open(arguments.grab).convert("L")
    width, height = image.size
    pixels = list(image.getdata())
    print("%s: %d by %d" % (arguments.grab, width, height))
    bands = [tuple(int(part) for part in band.split(":")) for band in arguments.band] or [(0, height - 1)]
    for first_row, last_row in bands:
        report_band(pixels, width, first_row, min(last_row, height - 1))


if __name__ == "__main__":
    main()
