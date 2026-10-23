"""Reading a PNG with nothing but the standard library.

The rows are built here and filtered with each of the five filters the format
has, so every way back to the pixels is taken. The grabs in `grabs/` are what
Previous wrote on a Pi 5 on 23.10.2026, so the shape being read is the shape
that exists: a blank screen and a Workspace in two-bit gray, and a NeXTdimension
in RGB, filtered by libpng's own choice row by row.
"""

import pathlib
import struct
import zlib

import pytest
from PIL import Image

from previously import png

GRABS = pathlib.Path(__file__).resolve().parent / "grabs"


def chunk(kind, data):
    """One chunk as the format lays it out."""
    return (struct.pack(">I", len(data)) + kind + data
            + struct.pack(">I", zlib.crc32(kind + data)))


def paeth(left, above, upper_left):
    """The predictor the format names after Alan Paeth."""
    estimate = left + above - upper_left
    near_left = abs(estimate - left)
    near_above = abs(estimate - above)
    near_upper_left = abs(estimate - upper_left)
    if near_left <= near_above and near_left <= near_upper_left:
        return left
    if near_above <= near_upper_left:
        return above
    return upper_left


def filtered(kind, row, above, distance):
    """A row filtered the way an encoder does it."""
    out = bytearray()
    for index, value in enumerate(row):
        left = row[index - distance] if index >= distance else 0
        upper_left = above[index - distance] if index >= distance else 0
        guess = {0: 0, 1: left, 2: above[index], 3: (left + above[index]) >> 1,
                 4: paeth(left, above[index], upper_left)}[kind]
        out.append((value - guess) & 0xFF)
    return bytes(out)


def encoded(rows, width, depth=8, colour=2, filters=None, interlace=0):
    """A PNG of these rows, each filtered with the type given for it."""
    channels = {0: 1, 2: 3}[colour]
    distance = max(1, channels * depth // 8)
    kinds = filters or [0] * len(rows)
    raw = b""
    above = bytes(len(rows[0]))
    for kind, row in zip(kinds, rows):
        raw += bytes([kind]) + filtered(kind, row, above, distance)
        above = row
    header = struct.pack(">IIBBBBB", width, len(rows), depth, colour, 0, 0, interlace)
    return (png.SIGNATURE + chunk(b"IHDR", header)
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def pattern(width, height):
    """RGB rows that differ from pixel to pixel and from row to row."""
    return [bytes((row * 37 + column * 11 + channel * 101) & 0xFF
                  for column in range(width) for channel in range(3))
            for row in range(height)]


@pytest.mark.parametrize("kind", [0, 1, 2, 3, 4])
def test_each_filter_comes_back_as_the_rows_it_was_made_from(kind):
    rows = pattern(7, 5)

    assert list(png.rows(encoded(rows, 7, filters=[kind] * 5))) == rows


def test_filters_that_change_from_row_to_row_come_back_too():
    rows = pattern(7, 5)

    assert list(png.rows(encoded(rows, 7, filters=[4, 0, 1, 3, 2]))) == rows


def test_a_flat_picture_is_one_color():
    rows = [bytes([0x55, 0x55, 0x55] * 7)] * 5

    assert png.one_color(encoded(rows, 7, filters=[1, 2, 4, 3, 0])) is True


def test_one_pixel_of_another_color_is_not():
    rows = [bytes([0x55, 0x55, 0x55] * 7)] * 5
    rows[3] = rows[3][:9] + bytes([0x56]) + rows[3][10:]

    assert png.one_color(encoded(rows, 7)) is False


def test_a_row_of_two_colors_is_not_one_color_even_where_every_row_matches():
    rows = [bytes([0x00, 0x00, 0x00, 0xFF, 0xFF, 0xFF])] * 3

    assert png.one_color(encoded(rows, 2)) is False


def test_two_bit_gray_is_read_four_pixels_to_a_byte():
    """The depth Previous writes a NeXTcube's screen in."""
    flat = [bytes([0x55] * 4)] * 3
    marked = [bytes([0x55] * 4), bytes([0x55, 0x54, 0x55, 0x55]), bytes([0x55] * 4)]

    assert png.one_color(encoded(flat, 16, depth=2, colour=0)) is True
    assert png.one_color(encoded(marked, 16, depth=2, colour=0)) is False


def test_a_byte_of_four_different_pixels_is_not_one_color():
    """0x1B holds the four grays 0, 1, 2 and 3, and every row is the same."""
    rows = [bytes([0x1B] * 4)] * 3

    assert png.one_color(encoded(rows, 16, depth=2, colour=0)) is False


def test_a_blank_screen_as_previous_grabbed_it_is_one_color():
    """A NeXTcube with NeXTdimension whose window showed the main screen while
    its console was on the board: every pixel the NeXT's dark gray."""
    assert png.one_color((GRABS / "blank.png").read_bytes()) is True


@pytest.mark.parametrize("name", ["workspace.png", "dimension.png"])
def test_a_workspace_as_previous_grabbed_it_is_not(name):
    assert png.one_color((GRABS / name).read_bytes()) is False


def test_a_grab_in_color_reads_as_pillow_reads_it():
    """libpng chose Sub, Up and Paeth for its rows."""
    path = GRABS / "dimension.png"
    picture = Image.open(path)
    width, height = picture.size
    expected = picture.convert("RGB").tobytes()

    found = b"".join(png.rows(path.read_bytes()))

    assert len(found) == width * height * 3
    assert found == expected


def test_what_is_not_a_png_cannot_be_read():
    with pytest.raises(png.Unreadable):
        png.one_color(b"not a picture at all")


def test_an_interlaced_picture_is_not_read():
    """Previous does not write one, and reading one is seven passes this does
    not need."""
    with pytest.raises(png.Unreadable):
        png.one_color(encoded(pattern(2, 2), 2, interlace=1))


def test_a_picture_cut_short_cannot_be_read():
    data = encoded(pattern(7, 5), 7)

    with pytest.raises(png.Unreadable):
        png.one_color(data[:len(data) // 2])


def test_a_filter_the_format_does_not_have_cannot_be_read():
    data = encoded(pattern(2, 2), 2, filters=[0, 0])
    raw = bytearray(zlib.decompress(data[data.index(b"IDAT") + 4:data.index(b"IEND") - 8]))
    raw[0] = 9
    header = data[8:8 + 25]
    broken = (png.SIGNATURE + header + chunk(b"IDAT", zlib.compress(bytes(raw)))
              + chunk(b"IEND", b""))

    with pytest.raises(png.Unreadable):
        png.one_color(broken)
