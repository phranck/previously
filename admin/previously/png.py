"""Reading the pixels of a PNG with the standard library alone.

The service imports nothing from outside it, so this is what reads the grabs
Previous writes. It reads the shapes Previous writes and no more: one image,
not interlaced, at any of the format's color types and depths. That covers a
NeXTcube's two-bit gray and a NeXTdimension's RGB, both measured on a Pi 5 on
23.10.2026.

Most of the work is undoing the filters. An encoder may filter each row with
one of five predictors from the PNG specification, section 9, and libpng picks
Sub, Up and Paeth row by row for a NeXTdimension's screen. Undoing them is a
loop over every byte, so `one_color` stops at the first row that settles the
question. Measured on a Pi 4 on 23.10.2026: a NeXTdimension's Workspace takes
26 ms, a NeXTcube's 1 ms, and a screen of one color in RGB with every row
filtered by Paeth, which nothing settles before the last row, 2.5 seconds.
"""

import struct
import zlib

#: How every PNG begins, from the specification, section 5.2.
SIGNATURE = b"\x89PNG\r\n\x1a\n"

#: How many samples a pixel has, by color type: gray, RGB, a palette index,
#: gray with alpha, and RGB with alpha.
CHANNELS = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}


class Unreadable(ValueError):
    """Bytes that are not a PNG this module reads."""


def one_color(data):
    """Whether every pixel of a picture is the same.

    @param data - The bytes of a PNG.
    @returns bool
    @raises Unreadable where the bytes are not a PNG this reads.

    Two questions in that order: whether the first row is one pixel repeated,
    and whether every other row is the first row again.
    """
    header, lines = _read(data)
    first = next(lines, None)
    if first is None or not _repeats_one_pixel(first, header):
        return False
    return all(line == first for line in lines)


def rows(data):
    """The rows of a picture, with every filter undone.

    @param data - The bytes of a PNG.
    @returns iterator of bytes, one per row, as the samples stand in the file:
      packed several to a byte below a depth of eight.
    @raises Unreadable where the bytes are not a PNG this reads.
    """
    return _read(data)[1]


def _read(data):
    """@returns (header, iterator of rows). @raises Unreadable."""
    header, compressed = _chunks(data)
    try:
        raw = zlib.decompress(compressed)
    except zlib.error as error:
        raise Unreadable(str(error)) from error
    if len(raw) < header["height"] * (header["stride"] + 1):
        raise Unreadable("the picture is shorter than its header says")
    return header, _unfiltered(raw, header)


def _chunks(data):
    """The header and the compressed pixels, out of the chunks.

    @returns (dict, bytes). The dict holds `width`, `height`, `depth`,
      `stride`, the bytes in one row, and `distance`, how far back the same
      sample of the pixel before lies.
    @raises Unreadable.
    """
    if not data.startswith(SIGNATURE):
        raise Unreadable("not a PNG")
    header = None
    compressed = []
    at = len(SIGNATURE)
    while at + 8 <= len(data):
        length, kind = struct.unpack(">I4s", data[at:at + 8])
        body = data[at + 8:at + 8 + length]
        if kind == b"IHDR":
            header = _header(body)
        elif kind == b"IDAT":
            compressed.append(body)
        elif kind == b"IEND":
            break
        at += 12 + length
    if header is None or not compressed:
        raise Unreadable("no header or no pixels")
    return header, b"".join(compressed)


def _header(body):
    """@returns dict of what IHDR says, as `_chunks` describes it."""
    try:
        width, height, depth, colour, _, _, interlace = struct.unpack(">IIBBBBB", body)
    except struct.error as error:
        raise Unreadable(str(error)) from error
    if colour not in CHANNELS or interlace != 0 or not width or not height:
        raise Unreadable("a color type, an interlace or a size this does not read")
    bits = CHANNELS[colour] * depth
    return {"width": width, "height": height, "depth": depth,
            "stride": (width * bits + 7) // 8, "distance": max(1, bits // 8)}


def _unfiltered(raw, header):
    """Yields each row with its filter undone, against the row before it."""
    stride = header["stride"]
    distance = header["distance"]
    above = bytes(stride)
    for start in range(0, header["height"] * (stride + 1), stride + 1):
        line = bytearray(raw[start + 1:start + 1 + stride])
        _undo(raw[start], line, above, distance)
        yield bytes(line)
        above = line


def _undo(kind, line, above, distance):
    """Undoes one row's filter in place.

    @param kind - The filter, 0 to 4, as the specification numbers them.
    @param line - bytearray of the filtered row, changed in place.
    @param above - The row before it, already undone, or zeros for the first.
    @param distance - How far back the same sample of the pixel before lies.
    @raises Unreadable for a filter the format does not have.
    """
    if kind == 0:
        return
    if kind == 1:
        for index in range(distance, len(line)):
            line[index] = (line[index] + line[index - distance]) & 0xFF
    elif kind == 2:
        for index in range(len(line)):
            line[index] = (line[index] + above[index]) & 0xFF
    elif kind == 3:
        for index in range(len(line)):
            left = line[index - distance] if index >= distance else 0
            line[index] = (line[index] + ((left + above[index]) >> 1)) & 0xFF
    elif kind == 4:
        for index in range(len(line)):
            if index >= distance:
                left, upper_left = line[index - distance], above[index - distance]
            else:
                left = upper_left = 0
            line[index] = (line[index] + _paeth(left, above[index], upper_left)) & 0xFF
    else:
        raise Unreadable("filter %d" % kind)


def _paeth(left, above, upper_left):
    """The predictor of filter 4, which picks whichever neighbour is nearest
    to their sum less the corner."""
    estimate = left + above - upper_left
    near_left = abs(estimate - left)
    near_above = abs(estimate - above)
    near_upper_left = abs(estimate - upper_left)
    if near_left <= near_above and near_left <= near_upper_left:
        return left
    if near_above <= near_upper_left:
        return above
    return upper_left


def _repeats_one_pixel(line, header):
    """Whether a row is one pixel over and over.

    Below a depth of eight a byte holds several pixels, so the first byte has
    to be one value repeated and every byte has to be the first. Bits past the
    last pixel of a row are padding and are not compared.
    """
    distance = header["distance"]
    if header["depth"] >= 8:
        return line == line[:distance] * (len(line) // distance)

    depth = header["depth"]
    mask = (1 << depth) - 1
    first = line[0]
    if any(((first >> shift) & mask) != (first & mask) for shift in range(0, 8, depth)):
        return False
    used = (header["width"] * depth) % 8
    whole = line if not used else line[:-1]
    if whole != bytes([first]) * len(whole):
        return False
    return not used or (line[-1] >> (8 - used)) == (first >> (8 - used))
