#!/usr/bin/env python3
"""Pulls the pictures the mockup uses out of their two real sources.

The icons come out of a NeXTSTEP 3.3 disk image. They sit in the Workspace
Manager's bundle as TIFFs in a shape no current library reads, so ufs.py walks
the filesystem and nxtiff.py decodes them. Each file holds the same picture
twice, in the four greys a mono NeXT could draw and in four bits per colour
channel, and the colour one is the one that ends up here.

The window buttons and the submenu arrow are not files at all. NeXTSTEP drew
them in PostScript at runtime, so they are cut out of a screenshot of the
running system at their own pixel bounds.

    python3 extract.py ~/nextstep/NS33_2GB.dd screenshot.png

Afterwards run build.py, which bakes parts/ into the mockup.
"""

import pathlib
import sys

from PIL import Image

import nxtiff
from ufs import UFS

HERE = pathlib.Path(__file__).parent
PARTS = HERE / "parts"

# Where the filesystem starts inside the image. A NeXT disk opens with a dlV3
# label, so the superblock is not at the front.
PARTITION_OFFSET = 163840

ICON_DIRECTORY = "/usr/lib/NextStep/Workspace.app/WM.app"

# Which icons to take, what each is called here, and what it is for. The
# purpose is written down so a later reader does not have to work out why these
# eleven and not the other twenty-six in that directory.
ICONS = {
    "root": ("root", "the machine, which NeXTSTEP drew the same for every host"),
    "winchester": ("winchester", "a hard disk"),
    "optical": ("optical", "an optical cartridge, the installation media"),
    "floppy": ("floppy", "a floppy disk"),
    "folder": ("folder", "a folder"),
    "net": ("net", "the network"),
    "scsi": ("scsi", "a SCSI device"),
    "defaultUnixIcon": ("defaultUnixIcon", "a Unix program, which the console is"),
    # NeXTSTEP's own icon for an application that brought none of its own.
    # Configure.app, which configured a real NeXT's hardware and would have
    # been the right picture for an editor of machine configurations, has no
    # icon in this image: the installation carries its bundles and neither
    # its executable nor its tiff. Searching the whole filesystem for one
    # named after configuring found only PrintManager's. So this is what an
    # application without a face of its own wore, which is what the config
    # editor is until it has one.
    "defaultAppIcon": ("defaultAppIcon", "an application, as NeXTSTEP drew one"),
    # In English.lproj rather than beside the others, which is where NeXT put
    # the few icons that were localised.
    "/usr/lib/NextStep/Workspace.app/WM.app/English.lproj/home":
        ("home", "a home directory, which NeXTSTEP drew as a house"),
    # Outside the Workspace's own directory, so it carries its whole path.
    "/NextApps/Terminal.app/icon": ("Terminal", "the terminal, for a shell session"),
    # Preferences.app kept a picture in each module's own bundle, at a size of
    # its own rather than at the 48 of a Workspace icon. This is the module
    # this tool offers, and the only one of the fourteen with anything to set
    # here.
    "/NextApps/Preferences.app/Localization.preferences/Localization":
        ("Localization", "the language the tool speaks, as Preferences drew it"),
    "/NextApps/Preferences.app/Preferences":
        ("Preferences", "the application itself, as it sat in NextApps"),
    # NeXT shipped an application for exactly this and called it Grab, so the
    # one here carries its name and its face. The camera is the picture inside
    # its own window rather than a Workspace icon, which is why it is 64 square
    # where the others are 48: Grab.app carries no icon file of its own, and
    # its Info.tiff is a photograph of whoever wrote it.
    "/NextApps/Grab.app/CameraNormal.tiff":
        ("Grab", "the camera Grab.app drew, for the application that takes a picture"),
    # What a picture of a screen wears in a viewer. From Preview, which is the
    # application that opened one, and it says TIFF because that is what
    # NeXTSTEP's pictures were and what this tool writes for it.
    "/NextApps/Preview.app/tiff.tiff":
        ("tiff", "a picture, as Preview.app drew one"),
    "Workspace": ("Workspace", "the NeXT wordmark on its cube"),
    "trash.1.alpha": ("trash", "the recycler, in the first of its four frames"),
    "hilite": ("hilite", "the white a selected icon sits on"),
}

# Where the interface parts sit in a 1120 by 832 screenshot of NeXTSTEP 3.3.
# These are pixel bounds, so a screenshot at another size will not do.
PARTS_IN_SCREENSHOT = {
    "wbtn-mini": (156, 16, 171, 31),
    "wbtn-close": (796, 305, 811, 320),
    # The three marks in the corner of a dock tile, which said the application
    # was NOT running: they are there whilst it is off and go when it starts.
    # Read off the running system, where Mail, Librarian and the console carry
    # them whilst the Workspace and the clock do not, and stated the same way
    # in the OpenStep User Interface Guidelines. Each is three pixels by two,
    # pressed into the face.
    "dock-marks": (1057, 186, 1070, 188),
}

def extract_icons(image_path):
    """Reads the icon TIFFs out of the disk image and writes them as PNG."""
    filesystem = UFS(str(image_path), PARTITION_OFFSET)
    written = 0
    for source, (name, _) in ICONS.items():
        # A name is taken from the Workspace's own directory unless it carries
        # a path of its own, which the few icons that live in an application
        # do.
        where = source if source.startswith("/") else "%s/%s" % (ICON_DIRECTORY, source)
        inode = filesystem.resolve(where + ".tiff")
        if inode is None:
            print("  missing in image: " + source)
            continue
        nxtiff.decode(filesystem.read(inode)).save(PARTS / (name + ".png"))
        written += 1
    return written


def extract_parts(screenshot_path):
    """Cuts the PostScript-drawn controls out of the screenshot."""
    shot = Image.open(screenshot_path).convert("RGBA")
    for name, box in PARTS_IN_SCREENSHOT.items():
        piece = shot.crop(box)
        if name == "dock-marks":
            # The marks are black and white alone, and whatever else is in the
            # crop is the tile behind them.
            clear(piece, lambda colour: colour not in ((0, 0, 0), (255, 255, 255)))
        piece.save(PARTS / (name + ".png"))
    return len(PARTS_IN_SCREENSHOT)


def clear(piece, matches):
    """Makes every pixel transparent whose colour the test accepts.

    @param matches - Takes an (r, g, b) triple and returns whether to clear it.
    """
    pixels = piece.load()
    for y in range(piece.height):
        for x in range(piece.width):
            if matches(pixels[x, y][:3]):
                pixels[x, y] = (0, 0, 0, 0)


def colour_tube():
    """Writes the colour variant of the machine icon.

    A NeXT with a NeXTdimension or a Trinitron showed a colour picture, and
    this is that same icon with that same tube lit. Every pixel keeps the
    brightness it had; only the hue is laid over it, so nothing is invented
    beyond the fact that the screen was on.
    """
    tube = (8, 5, 39, 27)
    bands = [(196, 120, 196), (110, 190, 130), (210, 190, 90)]

    picture = Image.open(PARTS / "root.png").convert("RGBA")
    pixels = picture.load()
    left, top, right, bottom = tube
    height = bottom - top

    for y in range(top, bottom):
        band = bands[min(len(bands) - 1, (y - top) * len(bands) // height)]
        for x in range(left, right):
            red, green, blue, alpha = pixels[x, y]
            if alpha == 0 or red + green + blue > 300:
                continue                    # the bezel and the glare stay put
            level = (red + green + blue) / 3 / 96
            pixels[x, y] = (min(255, int(band[0] * level)),
                            min(255, int(band[1] * level)),
                            min(255, int(band[2] * level)), alpha)
    picture.save(PARTS / "root-color.png")


def main():
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    PARTS.mkdir(exist_ok=True)
    icons = extract_icons(pathlib.Path(sys.argv[1]))
    controls = extract_parts(pathlib.Path(sys.argv[2]))
    colour_tube()
    print("wrote %d icons, %d controls and the colour tube into parts/" % (icons, controls))


if __name__ == "__main__":
    main()
