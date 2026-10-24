"""Draws the boot picture or the shutdown picture onto a framebuffer, or lays
the boot picture out for the initramfs to draw.

    python3 -m previously.splash fb0
    python3 -m previously.splash fb0 shutdown
    python3 -m previously.splash fb0 --into DIRECTORY

The package's initramfs hook runs the third while an initramfs is built. It
writes the whole screen as fb0 holds it at that moment, with the boot picture
in the middle, and what that screen is, in the form /sys/class/graphics/fb0
says it. The package's script in local-bottom copies the frame onto fb0 once
the root is mounted, where the console is switched on and fb0 is still that
screen. vc4 comes up in the initramfs as well, so that is the first moment
the Pi can show anything after the firmware.

previously-splash@.service runs the first when udev sees a framebuffer appear,
which on a Raspberry Pi is vc4's, and again when systemd replays udev's events
for one that appeared in the initramfs. It draws the same picture over the
initramfs's, and it is what draws it on a screen the initramfs had no frame
for. From there the picture stands until cage takes the screen.

previously-splash-shutdown.service runs the second when it stops, which on the
way down is after the console, so cage has given the screen back and the text
console has redrawn it. From there the picture stands until the Pi goes dark.

The kernel's own fullscreen logo cannot do this. It draws only on a framebuffer
that exists before `late_initcall_sync`, because `fb_find_logo` in
drivers/video/logo/logo.c answers nothing once `logos_freed` is set. vc4 is a
module and arrives later, so the logo is drawn on the firmware's framebuffer
alone, which stood for 1.4 s at 720 by 480 on a Pi 4 on 24.10.2026.

The pictures are the TGAs the package build writes, a pair for every board the
admin knows, and each board draws its own, as the admin's windows show it.
Like the kernel's logo a picture is never scaled: it is centred where it is
smaller than the screen and clipped evenly on both sides where it is larger.
Each pixel is written in the framebuffer's own format, as the kernel describes
it through
FBIOGET_VSCREENINFO, so the same picture is right at 16 bits a pixel on a Pi 4
and at whatever another board uses.

Drawing runs as an unprivileged user in the video group, which may write the
framebuffer and nothing else this needs. Laying out runs inside
update-initramfs, as root, and only reads the framebuffer.
"""

import fcntl
import pathlib
import struct
import sys

from . import hardware

#: Where the package keeps the pictures, and what each kind a caller asks for
#: is called there in front of the board it shows: the one shown while the Pi
#: starts and the one shown while it shuts down, so `splash-pi4.tga` is a Pi 4's
#: boot picture. `packaging/build.py` writes a pair for every board in
#: `hardware.BOARDS`, and `tests/test_packaging.py` holds the two to the same
#: names.
PICTURE_DIRECTORY = pathlib.Path("/usr/share/previously")
KINDS = {"boot": "splash", "shutdown": "splash-shutdown"}

#: The board whose pictures a board the service does not know shows, which is
#: what every board showed before each had pictures of its own.
FALLBACK_BOARD = "pi5"

#: Where the framebuffers are, by the name udev hands over.
DEVICES = pathlib.Path("/dev")

#: What the firmware's framebuffer is called, which simplefb names it
#: (drivers/video/fbdev/simplefb.c in raspberrypi/linux). vc4 takes the screen
#: from it at another mode, so nothing is drawn or laid out for it.
FIRMWARE_FRAMEBUFFER = "simple"

#: What the frame laid out for the initramfs and the screen it is for are
#: called, in the directory they are written into. `packaging/build.py` writes
#: the script that reads them with the same names.
FRAME = "frame"
GEOMETRY = "geometry"

#: The two requests from linux/fb.h, and the visual whose pixels are written as
#: red, green and blue bitfields.
FBIOGET_VSCREENINFO = 0x4600
FBIOGET_FSCREENINFO = 0x4602
FB_VISUAL_TRUECOLOR = 2

#: struct fb_var_screeninfo from linux/fb.h: forty unsigned 32 bit fields,
#: from xres to the last reserved one. The red, green and blue bitfields are
#: three each, offset, length and msb_right, starting at the ninth.
VAR_SCREENINFO = struct.Struct("=40I")

#: struct fb_fix_screeninfo from linux/fb.h, in the machine's own alignment,
#: because two of its fields are an unsigned long. The `0L` pads the end to
#: that alignment as the compiler does, because the kernel copies the whole of
#: its struct into the buffer and a shorter buffer would be written past.
FIX_SCREENINFO = struct.Struct("@16sLIIIIHHHILIIH2H0L")

#: The TGA's header, as packaging/build.py writes it: 18 bytes, the width and
#: the height at bytes 12 to 15, the depth at byte 16.
TGA_HEADER = 18


def stem(kind, board):
    """@returns str, what the picture of one kind for one board is called
    without its extension, such as `splash-pi4`, which is also what previous.li
    calls the PNG it is made from.

    @param kind - A key of KINDS.
    @param board - A name out of `hardware.BOARDS`.
    """
    return "%s-%s" % (KINDS[kind], board)


def stems():
    """@returns list of str, the stem of every picture there is: both kinds for
    every board in `hardware.BOARDS`, which is what the package carries and what
    design/mark.py fetches."""
    return [stem(kind, board) for board in sorted(set(hardware.BOARDS.values()))
            for kind in KINDS]


def picture_of(kind):
    """@returns pathlib.Path, the picture of one kind for the board this runs
    on, or FALLBACK_BOARD's on a board the service does not know.

    @param kind - A key of KINDS.
    """
    return PICTURE_DIRECTORY / (stem(kind, hardware.board() or FALLBACK_BOARD) + ".tga")


class Unsupported(Exception):
    """A framebuffer or a picture this does not draw."""


class Screen:
    """What a framebuffer is, as the kernel describes it.

    @param var - bytes of struct fb_var_screeninfo.
    @param fix - bytes of struct fb_fix_screeninfo.
    @raises Unsupported where its pixels are not red, green and blue
      bitfields in whole bytes.
    """

    def __init__(self, var, fix):
        fields = VAR_SCREENINFO.unpack(var)
        self.width, self.height = fields[0], fields[1]
        self.virtual_width, self.virtual_height = fields[2], fields[3]
        self.x_offset, self.y_offset = fields[4], fields[5]
        self.bits = fields[6]
        self.red, self.green, self.blue = fields[8:10], fields[11:13], fields[14:16]
        fixed = FIX_SCREENINFO.unpack(fix)
        self.name = fixed[0].split(b"\0", 1)[0].decode("ascii", "replace")
        self.visual = fixed[5]
        self.stride = fixed[9]
        if self.visual != FB_VISUAL_TRUECOLOR or self.bits % 8 or not self.bits:
            raise Unsupported("visual %d at %d bits a pixel" % (self.visual, self.bits))
        for offset, length in (self.red, self.green, self.blue):
            if not 0 < length <= 8 or offset + length > self.bits:
                raise Unsupported("a colour of %d bits at bit %d of %d"
                                  % (length, offset, self.bits))

    def pixel(self, red, green, blue):
        """@returns bytes, one pixel in this framebuffer's format, low byte
        first as the hardware stores it."""
        value = 0
        for sample, (offset, length) in ((red, self.red), (green, self.green),
                                         (blue, self.blue)):
            value |= (sample >> (8 - length)) << offset
        return value.to_bytes(self.bits // 8, "little")


def picture(data):
    """The boot picture's pixels.

    @param data - bytes of the TGA.
    @returns (int, int, bytes): its width, its height, and its pixels from the
      top row down, three bytes to a pixel in the order blue, green, red.
    @raises Unsupported where it is not the uncompressed true colour TGA the
      package build writes.
    """
    if len(data) < TGA_HEADER or data[2] != 2 or data[16] != 24 or not data[17] & 0x20:
        raise Unsupported("not the TGA the package writes")
    width, height = struct.unpack_from("<HH", data, 12)
    pixels = data[TGA_HEADER + data[0]:]
    if len(pixels) < width * height * 3:
        raise Unsupported("the picture is shorter than its header says")
    return width, height, pixels


def placed(size, screen):
    """Where a side of the picture goes on the same side of the screen.

    @param size - The picture's width or height.
    @param screen - The screen's width or height.
    @returns (int, int, int): where on the screen it starts, how much of the
      picture is clipped from each end, and how much of it is shown.
    """
    clipped = max(0, (size - screen) // 2)
    shown = size - 2 * clipped
    return (screen - shown) // 2, clipped, shown


def frame(data, screen):
    """The whole visible screen with the picture in the middle, as the
    framebuffer holds it.

    @param data - bytes of the TGA.
    @param screen - The Screen it is laid out for.
    @returns bytes, `screen.stride` bytes for each of the screen's lines, and
      black wherever the picture is not.
    @raises Unsupported as `picture` does.

    The whole screen rather than the picture's lines alone, so whatever the
    text console left on it, such as a line the kernel printed, is gone with
    everything else, and so the initramfs can put it onto the screen with one
    copy.
    """
    width, height, pixels = picture(data)
    out = bytearray(screen.stride * screen.height)
    left, skip_x, shown_x = placed(width, screen.width)
    top, skip_y, shown_y = placed(height, screen.height)
    size = screen.bits // 8
    # The picture has a few hundred colours, so each is turned into the
    # framebuffer's format once rather than once per pixel.
    formats = {}
    for row in range(shown_y):
        start = ((skip_y + row) * width + skip_x) * 3
        line = pixels[start:start + shown_x * 3]
        turned = bytearray()
        for at in range(0, len(line), 3):
            colour = line[at:at + 3]
            if colour not in formats:
                formats[colour] = screen.pixel(colour[2], colour[1], colour[0])
            turned += formats[colour]
        begins = (top + row) * screen.stride + left * size
        out[begins:begins + len(turned)] = turned
    return bytes(out)


def geometry(screen):
    """@returns str, what the screen is, as /sys/class/graphics/fb0 says it:
    `virtual_size`, `bits_per_pixel`, `stride` and `pan`, one after another,
    which on next5 on 24.10.2026 was `1024,600 16 2048 0,0`.

    @param screen - The Screen.

    The initramfs compares this with what sysfs says as text, because a shell
    there has nothing else to compare with. A frame laid out for one screen
    and copied onto another is torn rather than a picture.
    """
    return "%d,%d %d %d %d,%d\n" % (screen.virtual_width, screen.virtual_height,
                                    screen.bits, screen.stride,
                                    screen.x_offset, screen.y_offset)


def _screen_of(device):
    """@returns Screen, what the kernel says of an open framebuffer.

    @param device - The open file.
    @raises Unsupported as Screen does.
    """
    var = bytearray(VAR_SCREENINFO.size)
    fix = bytearray(FIX_SCREENINFO.size)
    fcntl.ioctl(device, FBIOGET_VSCREENINFO, var)
    fcntl.ioctl(device, FBIOGET_FSCREENINFO, fix)
    return Screen(bytes(var), bytes(fix))


def draw(name, picture_path=None, devices=None):
    """Draws the picture onto one framebuffer, as the whole of its screen.

    @param name - The framebuffer's name, such as `fb0`.
    @param picture_path - pathlib.Path of the TGA, this board's boot picture
      where left out.
    @param devices - Where the device files are, DEVICES where left out.
    @raises Unsupported, and OSError where the device cannot be opened.
    """
    data = (picture_path or picture_of("boot")).read_bytes()
    with open((devices or DEVICES) / name, "r+b", buffering=0) as device:
        screen = _screen_of(device)
        device.seek(screen.y_offset * screen.stride
                    + screen.x_offset * (screen.bits // 8))
        device.write(frame(data, screen))


def lay_out(name, into, devices=None):
    """Writes this board's boot picture as the whole of one framebuffer's
    screen, and what that screen is, for the initramfs to draw from.

    @param name - The framebuffer's name, such as `fb0`.
    @param into - pathlib.Path of the directory both go into, which is made
      where it is not there.
    @param devices - As `draw` takes it.
    @raises Unsupported where the framebuffer is the firmware's, and as `draw`
      raises.
    """
    data = picture_of("boot").read_bytes()
    with open((devices or DEVICES) / name, "rb") as device:
        screen = _screen_of(device)
    if screen.name == FIRMWARE_FRAMEBUFFER:
        raise Unsupported("it is the firmware's, which vc4 takes the screen from")
    laid = frame(data, screen)
    into.mkdir(parents=True, exist_ok=True)
    (into / FRAME).write_bytes(laid)
    (into / GEOMETRY).write_text(geometry(screen), encoding="utf-8")


def main(argv=None):
    """@returns int, the exit status.

    @param argv - The framebuffer's name, and optionally which of KINDS to
      draw, the boot picture where left out. Or the framebuffer's name, then
      `--into` and a directory, to lay the boot picture out there instead.
    """
    arguments = sys.argv[1:] if argv is None else argv
    into = None
    if len(arguments) == 3 and arguments[1] == "--into":
        into = pathlib.Path(arguments[2])
        arguments = arguments[:1]
    if not 1 <= len(arguments) <= 2 or "/" in arguments[0]:
        print("usage: python3 -m previously.splash fb0 [%s]\n"
              "       python3 -m previously.splash fb0 --into DIRECTORY"
              % "|".join(KINDS), file=sys.stderr)
        return 2
    name = arguments[0]
    if into is not None:
        try:
            lay_out(name, into)
        except (Unsupported, OSError) as failure:
            print("no boot picture laid out for %s: %s" % (name, failure),
                  file=sys.stderr)
            return 1
        return 0
    kind = arguments[1] if len(arguments) == 2 else "boot"
    if kind not in KINDS:
        print("no picture called %s" % kind, file=sys.stderr)
        return 2
    try:
        draw(name, picture_of(kind))
    except (Unsupported, OSError) as failure:
        print("no %s picture on %s: %s" % (kind, name, failure), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
