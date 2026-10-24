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


def screeninfo(width, height, bits, fields, stride, visual, name=b"vc4drmfb", pan=(0, 0)):
    """@returns (bytes, bytes), the two structs the kernel answers with.

    @param fields - ((offset, length) of red, of green, of blue).
    @param visual - The visual, as linux/fb.h numbers them.
    @param name - What the driver calls its framebuffer.
    @param pan - Where the visible part starts, across and down.
    """
    var = [0] * 40
    var[0], var[1], var[2], var[3] = width, height, width, height
    var[4], var[5] = pan
    var[6] = bits
    for index, (offset, length) in zip((8, 11, 14), fields):
        var[index], var[index + 1] = offset, length
    fix = splash.FIX_SCREENINFO.pack(name, 0, stride * height, 0, 0, visual,
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

    @returns a function taking width, height, bits, fields, the visual, the
      driver's name for it and how many bytes each line has beyond its pixels,
      which makes the file and answers with its path and its stride.
    """
    answers = {}

    def ioctl(device, request, buffer):
        buffer[:] = answers[request]

    monkeypatch.setattr(splash.fcntl, "ioctl", ioctl)

    def make(width, height, bits, fields, visual=splash.FB_VISUAL_TRUECOLOR,
             name=b"vc4drmfb", padding=0):
        stride = width * bits // 8 + padding
        var, fix = screeninfo(width, height, bits, fields, stride, visual, name)
        answers[splash.FBIOGET_VSCREENINFO] = var
        answers[splash.FBIOGET_FSCREENINFO] = fix
        device = tmp_path / "fb0"
        device.write_bytes(bytes(stride * height))
        return device, stride

    return make


def the_board(monkeypatch, tmp_path, board):
    """Has the module run on a board of that name, read its pictures from the
    test's directory and open the framebuffers there.

    @param board - What `hardware.board()` answers, None for a board the
      service does not know.
    @returns pathlib.Path, where the pictures go.
    """
    monkeypatch.setattr(splash.hardware, "board", lambda: board)
    share = tmp_path / "share"
    share.mkdir(exist_ok=True)
    monkeypatch.setattr(splash, "PICTURE_DIRECTORY", share)
    monkeypatch.setattr(splash, "DEVICES", tmp_path)
    return share


def put(share, kind, board, picture):
    """Puts a picture of one kind for one board where the module looks."""
    (share / (splash.stem(kind, board) + ".tga")).write_bytes(picture)


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
    put(the_board(monkeypatch, tmp_path, "pi5"), "boot", "pi5", tga(1, 1, (0, 0, 0)))

    assert splash.main(["fb7"]) == 1
    said = capsys.readouterr().err
    assert "no boot picture on fb7" in said
    assert "fb7" in said and "No such file" in said


def test_the_shutdown_picture_is_the_one_asked_for(tmp_path, framebuffer, monkeypatch):
    """Drawn by the same code as the boot picture, out of its own file."""
    framebuffer(1, 1, 32, XRGB8888)
    share = the_board(monkeypatch, tmp_path, "pi5")
    for kind, colour in (("boot", (0, 0, 0xFF)), ("shutdown", (0xFF, 0, 0))):
        put(share, kind, "pi5", tga(1, 1, colour))

    assert splash.main(["fb0", "shutdown"]) == 0
    assert (tmp_path / "fb0").read_bytes() == bytes([0, 0, 0xFF, 0])


@pytest.mark.parametrize("kind", ["boot", "shutdown"])
def test_a_board_shows_its_own_board(tmp_path, framebuffer, monkeypatch, kind):
    """A Pi 4 shows a Pi 4's board, as the admin's windows do, while it starts
    and while it shuts down."""
    framebuffer(1, 1, 32, XRGB8888)
    share = the_board(monkeypatch, tmp_path, "pi4")
    put(share, kind, "pi4", tga(1, 1, (0, 0xFF, 0)))
    put(share, kind, "pi5", tga(1, 1, (0, 0, 0xFF)))

    assert splash.main(["fb0", kind]) == 0
    assert (tmp_path / "fb0").read_bytes() == bytes([0, 0xFF, 0, 0])


def test_a_board_the_service_does_not_know_shows_the_pi_5s(
        tmp_path, framebuffer, monkeypatch):
    """Which is what every board showed before there was a picture for each."""
    framebuffer(1, 1, 32, XRGB8888)
    put(the_board(monkeypatch, tmp_path, None), "boot", "pi5", tga(1, 1, (0, 0, 0xFF)))

    assert splash.main(["fb0"]) == 0
    assert (tmp_path / "fb0").read_bytes() == bytes([0xFF, 0, 0, 0])


def test_the_initramfs_is_laid_out_for_the_board_it_is_built_on(tmp_path, framebuffer,
                                                                monkeypatch):
    """The hook runs on the board itself, so what it asks is that board."""
    framebuffer(1, 1, 32, XRGB8888)
    share = the_board(monkeypatch, tmp_path, "cm5")
    put(share, "boot", "cm5", tga(1, 1, (0, 0xFF, 0)))
    put(share, "boot", "pi5", tga(1, 1, (0, 0, 0xFF)))

    assert splash.main(["fb0", "--into", str(tmp_path / "initramfs")]) == 0
    assert (tmp_path / "initramfs" / splash.FRAME).read_bytes() == bytes([0, 0xFF, 0, 0])


@pytest.mark.parametrize("names", [b"raspberrypi,5-model-b\0brcm,bcm2712\0", None],
                         ids=["a Pi 5", "no device tree"])
def test_the_frame_says_which_board_it_was_laid_out_on(tmp_path, framebuffer, monkeypatch,
                                                       names):
    """A card moved into another Pi boots an initramfs laid out on the first,
    and the script tells the two apart by the device tree's names, as they
    stand in the file. A machine without a device tree writes nothing there,
    which no Pi's names match."""
    framebuffer(4, 2, 16, RGB565)
    boot_picture(tmp_path, monkeypatch)
    tree = tmp_path / "compatible"
    if names is not None:
        tree.write_bytes(names)
    monkeypatch.setattr(splash.hardware, "COMPATIBLE", tree)

    assert splash.main(["fb0", "--into", str(tmp_path / "initramfs")]) == 0

    assert (tmp_path / "initramfs" / splash.BOARD).read_bytes() == (names or b"")


def test_a_picture_nobody_has_is_refused(capsys):
    assert splash.main(["fb0", "farewell"]) == 2


def test_the_structs_are_as_long_as_the_kernels():
    """Measured on a Pi 4 with the C compiler on 24.10.2026: 160 and 80 bytes.
    A shorter buffer would have the kernel write past its end."""
    assert splash.VAR_SCREENINFO.size == 160
    assert splash.FIX_SCREENINFO.size == 80


def test_drawing_clears_what_the_screen_showed_beside_the_picture(tmp_path, framebuffer):
    """The picture is written as the whole screen, so text the console left
    there, such as a line the kernel printed, goes with what was under it."""
    device, stride = framebuffer(4, 2, 32, XRGB8888, padding=8)
    device.write_bytes(b"\xff" * (stride * 2))

    written = drawn(tmp_path, tga(2, 1, (0, 0, 0xFF)))

    assert [offset for offset in range(len(written)) if written[offset]] == [4, 8]


def boot_picture(tmp_path, monkeypatch, colour=(0xFF, 0x80, 0x10)):
    """Makes a boot picture of two pixels for a Pi 5, which the module draws
    from on a Pi 5, and has it open the framebuffers in the test's directory."""
    put(the_board(monkeypatch, tmp_path, "pi5"), "boot", "pi5", tga(2, 1, colour))


def test_the_frame_for_the_initramfs_is_what_drawing_writes(tmp_path, framebuffer,
                                                            monkeypatch):
    """The hook lays the boot picture out for the screen as it is, and the
    initramfs copies it onto the screen as it stands, so the two have to be
    the same bytes."""
    framebuffer(4, 2, 16, RGB565, padding=4)
    boot_picture(tmp_path, monkeypatch)

    assert splash.main(["fb0", "--into", str(tmp_path / "initramfs")]) == 0
    laid_out = (tmp_path / "initramfs" / splash.FRAME).read_bytes()
    assert splash.main(["fb0"]) == 0

    assert laid_out == (tmp_path / "fb0").read_bytes()


def test_the_geometry_is_said_the_way_sysfs_says_it(tmp_path, framebuffer, monkeypatch):
    """virtual_size, bits_per_pixel, stride and pan, in that order and form, as
    /sys/class/graphics/fb0 gives them: `1024,600 16 2048 0,0` on next5 on
    24.10.2026. The initramfs compares the two as text."""
    framebuffer(1024, 600, 16, RGB565)
    boot_picture(tmp_path, monkeypatch)

    assert splash.main(["fb0", "--into", str(tmp_path / "initramfs")]) == 0

    said = (tmp_path / "initramfs" / splash.GEOMETRY).read_text(encoding="utf-8")
    assert said == "1024,600 16 2048 0,0\n"


def test_no_frame_is_laid_out_for_the_firmwares_framebuffer(tmp_path, framebuffer,
                                                            monkeypatch, capsys):
    """vc4 takes the screen from it, so a frame laid out for it is one the
    initramfs would never find a screen for."""
    framebuffer(4, 2, 32, XRGB8888, name=splash.FIRMWARE_FRAMEBUFFER.encode())
    boot_picture(tmp_path, monkeypatch)
    into = tmp_path / "initramfs"

    assert splash.main(["fb0", "--into", str(into)]) == 1
    assert not into.exists()
    assert "firmware" in capsys.readouterr().err
