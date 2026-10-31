#!/usr/bin/env python3
"""Cuts NeXTSTEP's switch, radio button, knob dimple and scroller arrows out of
two grabs of the running system.

    python3 controls.py

The Application Kit drew both from bitmaps it compiled into its own library,
NXswitch, NXswitchH, NXradio and NXradioH in libNeXT_s, so they are not files
in the disk image that extract.py could read, and so did it the dimple a
scroller's knob carries and the arrows at the foot of its bar. Preferences
shows all of them: its Expert module has a switch off and one on, its Mouse
module a radio button on and one off, and the File Viewer behind it a
scroller with its knob and both arrows. grabs/ holds those two screens, grabbed with the
emulator's own Ctrl+Alt+G on next5 on 26 October 2026 at the machine's
1120 by 832.

Each control is cut at its own pixel bounds into ../admin/web/parts/, the
folder the admin serves its pictures from, gray face and all: the kit lays
them on the same gray, so nothing has to be taken out. The left and right
arrows are the up arrow turned, because the one scroller in the grabs that
runs across is cut off before its arrows.
"""

import pathlib

from PIL import Image

HERE = pathlib.Path(__file__).parent
GRABS = HERE / "grabs"
#: Where the controls go: beside every other picture the admin serves.
PARTS = HERE.parent / "admin" / "web" / "parts"

#: Each control, the grab it is cut from, and its bounds as (left, top, right,
#: bottom), right and bottom exclusive. The switches and radio buttons are 15
#: by 15, the dimple 6 by 6 and the arrows 9 by 9.
CONTROLS = {
    "switch": ("preferences-expert.png", (583, 393, 598, 408)),
    "switch-on": ("preferences-expert.png", (583, 458, 598, 473)),
    "radio": ("preferences-mouse.png", (626, 405, 641, 420)),
    "radio-on": ("preferences-mouse.png", (626, 387, 641, 402)),
    "dimple": ("preferences-mouse.png", (207, 363, 213, 369)),
    "arrow-up": ("preferences-mouse.png", (206, 499, 215, 508)),
    "arrow-down": ("preferences-mouse.png", (206, 516, 215, 525)),
}

#: The arrows the grabs do not show, each as one they do turned, and by how
#: many degrees counter-clockwise.
TURNED = {
    "arrow-left": ("arrow-up", 90),
    "arrow-right": ("arrow-up", 270),
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
    for name, (source, degrees) in TURNED.items():
        cut(source).rotate(degrees).save(path(name))
    print("wrote " + ", ".join(path(name).name for name in [*CONTROLS, *TURNED]))


if __name__ == "__main__":
    main()
