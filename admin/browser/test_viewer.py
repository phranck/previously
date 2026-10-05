"""The File Viewer, held to showing what a machine that is set up holds.

A machine that is set up has a disk, so its root holds Apps, Disks, Documents
and Machines, and Discs as well once somebody has put a disc there. At the
width the window opens at that is two rows of icons, and a window that opens
on a second row cut in half has a knob for something nobody asked to scroll.
"""

import time

#: The contents band of the File Viewer against what it holds: how far the
#: icons run past the band, and how many there are.
CONTENTS = """
const view = document.querySelector("#file-viewer nx-scroller:not(.way)").view;
return { over: view.scrollHeight - view.clientHeight,
         things: view.querySelectorAll("nx-thing").length };
"""


def test_the_file_viewer_opens_with_the_whole_root_showing(desk):
    """The root of a home with a disk and a disc is five folders, and the
    window opens tall enough to show all of them without scrolling."""
    desk.execute_script("document.querySelector('nx-window[name=files]').open()")
    time.sleep(0.6)
    contents = desk.execute_script(CONTENTS)
    assert contents["things"] == 5, "the root should hold five folders here"
    assert contents["over"] <= 0, "the second row is cut by %d" % contents["over"]
