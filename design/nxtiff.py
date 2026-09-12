#!/usr/bin/env python3
"""Decode the TIFFs NeXTSTEP shipped its icons in.

They are ordinary uncompressed TIFFs, but in a shape no current library reads:
two bits per sample, two or more samples per pixel with the last one an alpha
channel, and the samples sometimes in separate planes. A NeXT could draw four
greys, so two bits is the whole of its greyscale.

Most icon files hold the same picture twice, once in those four greys and once
in four bits per colour channel, so every directory is decoded and the richer
one wins."""

import struct
from PIL import Image

TAG_WIDTH = 256
TAG_HEIGHT = 257
TAG_BPS = 258
TAG_COMPRESSION = 259
TAG_PHOTOMETRIC = 262
TAG_STRIP_OFFSETS = 273
TAG_SAMPLES = 277
TAG_STRIP_COUNTS = 279
TAG_PLANAR = 284

TYPE_SIZE = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8}
TYPE_FORMAT = {1: "B", 3: "H", 4: "I", 5: "I"}


def _values(data, tag_type, count, raw_offset, offset_position):
    """Reads a tag's values, following the offset when they do not fit inline."""
    size = TYPE_SIZE.get(tag_type, 1) * count
    base = raw_offset if size > 4 else offset_position
    fmt = TYPE_FORMAT.get(tag_type, "B")
    step = {"B": 1, "H": 2, "I": 4}[fmt]
    return [struct.unpack_from(">" + fmt, data, base + index * step)[0]
            for index in range(count)]


def _directories(data):
    """@returns a list of tag dictionaries, one per image in the file."""
    if data[:2] != b"MM":
        raise ValueError("not a big endian TIFF")
    offset, = struct.unpack_from(">I", data, 4)
    found = []
    while offset and offset < len(data) - 2:
        count, = struct.unpack_from(">H", data, offset)
        tags = {}
        for index in range(count):
            position = offset + 2 + index * 12
            tag, tag_type, values = struct.unpack_from(">HHI", data, position)
            raw, = struct.unpack_from(">I", data, position + 8)
            tags[tag] = _values(data, tag_type, values, raw, position + 8)
        found.append(tags)
        offset, = struct.unpack_from(">I", data, offset + 2 + count * 12)
    return found


def _lzw(data):
    """TIFF's LZW, which is LZW with the code width growing one step early."""
    out = bytearray()
    table = [bytes([index]) for index in range(256)] + [b"", b""]
    width, previous = 9, None
    value = bits = 0
    for byte in data:
        value = (value << 8) | byte
        bits += 8
        while bits >= width:
            code = (value >> (bits - width)) & ((1 << width) - 1)
            bits -= width
            if code == 256:
                table = table[:258]
                width, previous = 9, None
                continue
            if code == 257:
                return bytes(out)
            if previous is None:
                entry = table[code]
            elif code < len(table):
                entry = table[code]
                table.append(previous + entry[:1])
            else:
                entry = previous + previous[:1]
                table.append(entry)
            out += entry
            previous = entry
            if len(table) + 1 >= (1 << width) and width < 12:
                width += 1
    return bytes(out)


def _strip_bytes(data, tags, plane, planes):
    """The bytes of one plane, or of the whole image when the samples are
    interleaved rather than kept apart."""
    offsets = tags[TAG_STRIP_OFFSETS]
    counts = tags[TAG_STRIP_COUNTS]
    if tags.get(TAG_PLANAR, [1])[0] == 2:
        per_plane = max(1, len(offsets) // planes)
        offsets = offsets[plane * per_plane:(plane + 1) * per_plane]
        counts = counts[plane * per_plane:(plane + 1) * per_plane]
    raw = b"".join(data[start:start + length] for start, length in zip(offsets, counts))
    return _lzw(raw) if tags.get(TAG_COMPRESSION, [1])[0] == 5 else raw


def _unpack(raw, width, height, bits, sample, per_pixel):
    """Reads one sample of every pixel out of a packed, row-aligned bitmap.

    @param bits - The width of one sample, 2 for NeXT's greys and 4 for each
      channel of its colour icons.
    @param sample - Which sample to take, counting from zero.
    @param per_pixel - How many samples one pixel holds in this bitmap, so 1
      when the planes are separate and the full count when interleaved.
    """
    row_bytes = (width * bits * per_pixel + 7) // 8
    top = (1 << bits) - 1
    out = []
    for row in range(height):
        line = raw[row * row_bytes:(row + 1) * row_bytes]
        for column in range(width):
            bit = (column * per_pixel + sample) * bits
            index = bit // 8
            byte = line[index] if index < len(line) else 0
            out.append(((byte >> (8 - bits - bit % 8)) & top) * 255 // top)
    return out


def _image(data, tags):
    """@returns one directory rendered as RGBA, or None when it cannot be."""
    if tags.get(TAG_COMPRESSION, [1])[0] not in (1, 5):
        return None
    width, height = tags[TAG_WIDTH][0], tags[TAG_HEIGHT][0]
    bits = tags.get(TAG_BPS, [8])
    count = tags.get(TAG_SAMPLES, [1])[0]
    if count not in (1, 2, 3, 4) or len(bits) < count:
        return None

    interleaved = tags.get(TAG_PLANAR, [1])[0] == 1
    per_pixel = count if interleaved else 1

    def channel(index):
        raw = _strip_bytes(data, tags, 0 if interleaved else index, count)
        return _unpack(raw, width, height, bits[index],
                       index if interleaved else 0, per_pixel)

    first = channel(0)
    if tags.get(TAG_PHOTOMETRIC, [1])[0] == 0:
        first = [255 - value for value in first]

    if count >= 3:
        pixels = list(zip(first, channel(1), channel(2),
                          channel(3) if count == 4 else [255] * len(first)))
    else:
        alpha = channel(1) if count == 2 else [255] * len(first)
        pixels = [(value, value, value, a) for value, a in zip(first, alpha)]

    image = Image.new("RGBA", (width, height))
    image.putdata(pixels[:width * height])
    return image


def decode(data):
    """@returns the richest readable image in the file, as RGBA."""
    best = None
    for tags in _directories(data):
        image = _image(data, tags)
        if image is None:
            continue
        depth = sum(tags.get(TAG_BPS, [8]))
        if best is None or depth > best[0]:
            best = (depth, image)
    if best is None:
        raise ValueError("no readable image in file")
    return best[1]


if __name__ == "__main__":
    import sys
    decode(open(sys.argv[1], "rb").read()).save(sys.argv[2])
