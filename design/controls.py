#!/usr/bin/env python3
"""Cuts NeXTSTEP's switch and radio button out of two grabs of the running system.

    python3 controls.py

The Application Kit drew both from bitmaps it compiled into its own library,
NXswitch, NXswitchH, NXradio and NXradioH in libNeXT_s, so they are not files
in the disk image that extract.py could read. Preferences shows all four:
its Expert module has a switch off and one on, and its Mouse module a radio
button on and one off. grabs/ holds those two screens, grabbed with the
emulator's own Ctrl+Alt+G on next5 on 26 October 2026 at the machine's
1120 by 832.

Each control is cut at its own pixel bounds into ../admin/web/parts/, the
folder the admin serves its pictures from, gray face and all: the kit lays
them on the same gray, so nothing has to be taken out.
"""

import pathlib

from PIL import Image

HERE = pathlib.Path(__file__).parent
GRABS = HERE / "grabs"
#: Where the controls go: beside every other picture the admin serves.
PARTS = HERE.parent / "admin" / "web" / "parts"

#: Each control, the grab it is cut from, and its bounds as (left, top, right,
#: bottom), right and bottom exclusive. All four are 15 by 15.
CONTROLS = {
    "switch": ("preferences-expert.png", (583, 393, 598, 408)),
    "switch-on": ("preferences-expert.png", (583, 458, 598, 473)),
    "radio": ("preferences-mouse.png", (626, 405, 641, 420)),
    "radio-on": ("preferences-mouse.png", (626, 387, 641, 402)),
}


def cut(name):
    """@returns PIL.Image of one control, as the grab holds it."""
    grab, box = CONTROLS[name]
    return Image.open(GRABS / grab).convert("RGB").crop(box)


def path(name):
    """@returns pathlib.Path the control is written to."""
    return PARTS / f"{name}.png"


def main():
    for name in CONTROLS:
        cut(name).save(path(name))
    print("wrote " + ", ".join(path(name).name for name in CONTROLS))


if __name__ == "__main__":
    main()
