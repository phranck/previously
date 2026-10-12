"""Which board the service runs on.

The board is recognized by the names its device tree gives it rather than by
the sentence it is described with. The device tree's root `compatible` is a
list of names, the most specific first, each a vendor and a board such as
`raspberrypi,5-model-b`, and every one of them is fixed by that vendor's
binding schema in the kernel. Its `model` is free text: Raspberry Pi's firmware
rewrites it at boot, so a Pi 5 the kernel calls "Raspberry Pi 5" reports
"Raspberry Pi 5 Model B Rev 1.1", and a vendor's kernel words a board
differently from the mainline one. So the model is what a person reads under
the board's picture, and `compatible` is what decides which board it is.

Both are files the kernel holds in memory, and reading them costs nothing worth
counting, which is why Activity Monitor can ask for them twice a second.
"""

import pathlib

#: Where the device tree describes the board in a sentence, and where it names
#: it. Named rather than written into each function, so a test points them at
#: files of its own.
MODEL = pathlib.Path("/proc/device-tree/model")
COMPATIBLE = pathlib.Path("/proc/device-tree/compatible")

#: The boards Previously knows, by a name out of their device tree's root
#: `compatible`, each with the name the service gives it. The interface shows
#: the drawing called `board-<that name>.svg` in web/parts, and
#: tests/test_hardware.py holds every entry here to one. A board joins with an
#: entry here and its drawing.
#:
#: A Compute Module 5 Lite carries the Compute Module 5's name. A Pi 400 and a
#: Pi 500 carry names of their own, which are not here.
BOARDS = {
    "raspberrypi,4-model-b": "pi4",
    "raspberrypi,4-compute-module": "cm4",
    "raspberrypi,5-model-b": "pi5",
    "raspberrypi,5-compute-module": "cm5",
}


def model():
    """@returns The board's description, such as "Raspberry Pi 5 Model B Rev
      1.1", or None. For a person to read: what decides which board this is
      is `board()`."""
    try:
        raw = MODEL.read_bytes()
    except OSError:
        return None
    # The device tree writes its strings with a trailing null.
    return raw.decode("ascii", "replace").rstrip("\x00").strip() or None


def compatible():
    """@returns list of the names in the device tree's root `compatible`, the
      most specific first, such as ["raspberrypi,5-model-b", "brcm,bcm2712"],
      or None where there is no device tree to read."""
    try:
        raw = COMPATIBLE.read_bytes()
    except OSError:
        return None
    # The names stand one after the other, each ending in a null.
    names = [name.decode("ascii", "replace") for name in raw.split(b"\x00") if name]
    return names or None


def board():
    """@returns The name the service gives the board, one of the values of
      BOARDS, or None for a board it does not know.

    The first name in the list that BOARDS holds decides. The list runs from
    the most specific name to the most general, so an entry for a whole family
    also covers each revision of it that lists the family's name after its own.
    """
    for name in compatible() or ():
        if name in BOARDS:
            return BOARDS[name]
    return None
