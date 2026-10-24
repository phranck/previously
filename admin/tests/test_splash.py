"""The boot picture, drawn onto a framebuffer that is a file in the test's own
directory.

What is tested is what decides the picture on the screen: where it goes, how
much of it is clipped, and how every pixel is written in the framebuffer's own
format. The kernel's two answers about the framebuffer are replaced, because a
test has no framebuffer to ask, so they are built here the way linux/fb.h lays
them out.
"""

import struct

import pytest

from previously import splash


def tga(width, height, colour):
    """@returns bytes, a TGA of one colour as packaging/build.py writes one.

    @param colour - (red, green, blue).
    """
    red, green, blue = colour
    header = struct.pack("<BBBHHBHHHHBB", 0, 0, 2, 0, 0, 0, 0, 0, width, height, 24, 0x20)
    return header + bytes([blue, green, red]) * (width * height)


def screeninfo(width, height, bits, fields, stride, visual):
    """@returns (bytes, bytes), the two structs the kernel answers with.

    @param fields - ((offset, length) of red, of green, of blue).
    @param visual - The visual, as linux/fb.h numbers them.
    """
    var = [0] * 40
    var[0], var[1], var[2], var[3] = width, height, width, height
    var[6] = bits
    for index, (offset, length) in zip((8, 11, 14), fields):
        var[index], var[index + 1] = offset, length
    fix = splash.FIX_SCREENINFO.pack(b"vc4drmfb", 0, stride * height, 0, 0, visual,
                                     0, 0, 0, stride, 0, 0, 0, 0, 0, 0)
    return splash.VAR_SCREENINFO.pack(*var), fix


#: The visual of a framebuffer whose pixels are indices into a palette.
FB_VISUAL_PSEUDOCOLOR = 3


#: What vc4's framebuffer is on a Pi 4 and a Pi 5, read on 24.10.2026, and what
#: the firmware's was on a Pi 4.
RGB565 = ((11, 5), (5, 6), (0, 5))
XRGB8888 = ((16, 8), (8, 8), (0, 8))


@pytest.fixture
def framebuffer(tmp_path, monkeypatch):
    """A framebuffer as a file, and the kernel's answers about it.

    @returns a function taking width, height, bits, fields and the visual,
      which makes the file and answers with its path and its stride.
    """
    answers = {}

    def ioctl(device, request, buffer):
        buffer[:] = answers[request]

    monkeypatch.setattr(splash.fcntl, "ioctl", ioctl)

    def make(width, height, bits, fields, visual=splash.FB_VISUAL_TRUECOLOR):
        stride = width * bits // 8
        var, fix = screeninfo(width, height, bits, fields, stride, visual)
        answers[splash.FBIOGET_VSCREENINFO] = var
        answers[splash.FBIOGET_FSCREENINFO] = fix
        device = tmp_path / "fb0"
        device.write_bytes(bytes(stride * height))
        return device, stride

    return make


def drawn(tmp_path, picture):
    """Draws a picture onto fb0 in the test's directory. @returns its bytes."""
    path = tmp_path / "splash.tga"
    path.write_bytes(picture)
    splash.draw("fb0", path, tmp_path)
    return (tmp_path / "fb0").read_bytes()


def test_the_picture_stands_in_the_middle(tmp_path, framebuffer):
    """Never scaled and centred, as the kernel's own logo is."""
    device, stride = framebuffer(10, 6, 32, XRGB8888)

    written = drawn(tmp_path, tga(4, 2, (255, 255, 255)))

    lit = [(offset % stride // 4, offset // stride)
           for offset in range(0, len(written), 4) if written[offset:offset + 4] != bytes(4)]
    assert lit == [(x, y) for y in (2, 3) for x in (3, 4, 5, 6)]


def test_a_picture_wider_than_the_screen_is_clipped_evenly(tmp_path, framebuffer):
    """The board stays in the middle, and the trail and the black beside it
    lose the same on either side, which is how the picture is laid out."""
    framebuffer(4, 2, 32, XRGB8888)
    path = tmp_path / "splash.tga"
    header = struct.pack("<BBBHHBHHHHBB", 0, 0, 2, 0, 0, 0, 0, 0, 8, 1, 24, 0x20)
    # Eight pixels, each one's blue its own place in the row.
    path.write_bytes(header + b"".join(bytes([x, 0, 0]) for x in range(8)))

    splash.draw("fb0", path, tmp_path)
    first_row = (tmp_path / "fb0").read_bytes()[:16]

    assert [first_row[offset] for offset in range(0, 16, 4)] == [2, 3, 4, 5]


def test_sixteen_bits_a_pixel_is_red_green_and_blue_in_five_six_and_five(
        tmp_path, framebuffer):
    """What vc4's framebuffer is on a Pi 4 and a Pi 5."""
    framebuffer(1, 1, 16, RGB565)

    written = drawn(tmp_path, tga(1, 1, (0xFF, 0x80, 0x10)))

    assert written == struct.pack("<H", (0xFF >> 3) << 11 | (0x80 >> 2) << 5 | 0x10 >> 3)


def test_thirty_two_bits_a_pixel_is_blue_green_red_and_a_spare_byte(
        tmp_path, framebuffer):
    """What the firmware's framebuffer is on a Pi 4, low byte first."""
    framebuffer(1, 1, 32, XRGB8888)

    written = drawn(tmp_path, tga(1, 1, (0xFF, 0x80, 0x10)))

    assert written == bytes([0x10, 0x80, 0xFF, 0])


def test_a_framebuffer_that_is_not_true_colour_is_left_alone(tmp_path, framebuffer):
    """A palette's indices are no colours this could write."""
    framebuffer(1, 1, 8, ((0, 8), (0, 8), (0, 8)), FB_VISUAL_PSEUDOCOLOR)

    with pytest.raises(splash.Unsupported):
        drawn(tmp_path, tga(1, 1, (0xFF, 0xFF, 0xFF)))


def test_colours_that_do_not_fit_the_pixel_are_left_alone(tmp_path, framebuffer):
    """A framebuffer that says so is one this does not understand, and a pixel
    written past its own bytes lands on the next one."""
    framebuffer(1, 1, 8, RGB565)

    with pytest.raises(splash.Unsupported):
        drawn(tmp_path, tga(1, 1, (0xFF, 0xFF, 0xFF)))


@pytest.mark.parametrize("damage", [
    lambda picture: picture[:10],
    lambda picture: picture[:2] + b"\x0a" + picture[3:],
    lambda picture: picture[:-1],
])
def test_a_picture_that_is_not_the_packages_is_refused(damage):
    """Too short for its header, compressed, or shorter than it says."""
    with pytest.raises(splash.Unsupported):
        splash.picture(damage(tga(2, 2, (0, 0, 0))))


def test_the_name_has_to_be_a_framebuffers(capsys):
    """udev hands over a kernel name, and anything holding a separator is a
    path this does not open."""
    assert splash.main(["../tty1"]) == 2


def test_a_framebuffer_that_is_not_there_ends_quietly(tmp_path, monkeypatch, capsys):
    """The boot goes on without its picture, and the journal says why."""
    picture = tmp_path / "splash.tga"
    picture.write_bytes(tga(1, 1, (0, 0, 0)))
    monkeypatch.setattr(splash, "PICTURE", picture)
    monkeypatch.setattr(splash, "DEVICES", tmp_path)

    assert splash.main(["fb7"]) == 1
    said = capsys.readouterr().err
    assert "no boot picture on fb7" in said
    assert "fb7" in said and "No such file" in said


def test_the_structs_are_as_long_as_the_kernels():
    """Measured on a Pi 4 with the C compiler on 24.10.2026: 160 and 80 bytes.
    A shorter buffer would have the kernel write past its end."""
    assert splash.VAR_SCREENINFO.size == 160
    assert splash.FIX_SCREENINFO.size == 80
