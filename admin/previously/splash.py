"""Draws the boot picture or the shutdown picture onto a framebuffer.

    python3 -m previously.splash fb0
    python3 -m previously.splash fb0 shutdown

previously-splash@.service runs the first when udev sees a framebuffer appear,
which on a Raspberry Pi is the moment vc4 takes the screen over from the
firmware. From there the picture stands until cage sets the screen's mode.

previously-splash-shutdown.service runs the second when it stops, which on the
way down is after the console, so cage has given the screen back and the text
console has redrawn it. From there the picture stands until the Pi goes dark.

The kernel's own fullscreen logo cannot do this. It draws only on a framebuffer
that exists before `late_initcall_sync`, because `fb_find_logo` in
drivers/video/logo/logo.c answers nothing once `logos_freed` is set. vc4 is a
module and arrives later, so the logo is drawn on the firmware's framebuffer
alone, which stood for 1.4 s at 720 by 480 on a Pi 4 on 24.10.2026.

The picture is the TGA the package build writes. Like the kernel's logo it is
never scaled: it is centred where it is smaller than the screen and clipped
evenly on both sides where it is larger. Each pixel is written in the
framebuffer's own format, as the kernel describes it through
FBIOGET_VSCREENINFO, so the same picture is right at 16 bits a pixel on a Pi 4
and at whatever another board uses.

It runs as an unprivileged user in the video group, which may write the
framebuffer and nothing else this needs.
"""

import fcntl
import pathlib
import struct
import sys

#: The pictures, by the name a caller asks for: the one shown while the Pi
#: starts and the one shown while it shuts down. `packaging/build.py` writes
#: them there, and `tests/test_packaging.py` holds the two to the same paths.
PICTURES = {
    "boot": pathlib.Path("/usr/share/previously/splash.tga"),
    "shutdown": pathlib.Path("/usr/share/previously/splash-shutdown.tga"),
}

#: Where the framebuffers are, by the name udev hands over.
DEVICES = pathlib.Path("/dev")

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
        self.x_offset, self.y_offset = fields[4], fields[5]
        self.bits = fields[6]
        self.red, self.green, self.blue = fields[8:10], fields[11:13], fields[14:16]
        fixed = FIX_SCREENINFO.unpack(fix)
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


def draw(name, picture_path=None, devices=None):
    """Draws the picture onto one framebuffer.

    @param name - The framebuffer's name, such as `fb0`.
    @param picture_path - pathlib.Path of the TGA, the boot picture where left
      out.
    @param devices - Where the device files are, DEVICES where left out.
    @raises Unsupported, and OSError where the device cannot be opened.
    """
    width, height, pixels = picture((picture_path or PICTURES["boot"]).read_bytes())
    with open((devices or DEVICES) / name, "r+b", buffering=0) as device:
        var = bytearray(VAR_SCREENINFO.size)
        fix = bytearray(FIX_SCREENINFO.size)
        fcntl.ioctl(device, FBIOGET_VSCREENINFO, var)
        fcntl.ioctl(device, FBIOGET_FSCREENINFO, fix)
        screen = Screen(bytes(var), bytes(fix))

        left, skip_x, shown_x = placed(width, screen.width)
        top, skip_y, shown_y = placed(height, screen.height)
        # The picture has a few hundred colours, so each is turned into the
        # framebuffer's format once rather than once per pixel.
        formats = {}
        for row in range(shown_y):
            start = ((skip_y + row) * width + skip_x) * 3
            line = pixels[start:start + shown_x * 3]
            out = bytearray()
            for at in range(0, len(line), 3):
                colour = line[at:at + 3]
                if colour not in formats:
                    formats[colour] = screen.pixel(colour[2], colour[1], colour[0])
                out += formats[colour]
            device.seek((screen.y_offset + top + row) * screen.stride
                        + (screen.x_offset + left) * (screen.bits // 8))
            device.write(out)


def main(argv=None):
    """@returns int, the exit status.

    @param argv - The framebuffer's name, and optionally which of PICTURES to
      draw, the boot picture where left out.
    """
    arguments = sys.argv[1:] if argv is None else argv
    if not 1 <= len(arguments) <= 2 or "/" in arguments[0]:
        print("usage: python3 -m previously.splash fb0 [%s]" % "|".join(PICTURES),
              file=sys.stderr)
        return 2
    kind = arguments[1] if len(arguments) == 2 else "boot"
    if kind not in PICTURES:
        print("no picture called %s" % kind, file=sys.stderr)
        return 2
    try:
        draw(arguments[0], PICTURES[kind])
    except (Unsupported, OSError) as failure:
        print("no %s picture on %s: %s" % (kind, arguments[0], failure), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
