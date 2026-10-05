"""Preferences' row of modules, held to showing each module's picture whole.

The pictures are bitmaps out of Preferences.app, each at a size of its own, and
every pixel in them was set by hand. A cell that is smaller inside than its
picture cuts a row of the original off at an edge, and a row of cells taller
than its band leaves a pixel of overflow that nothing on the screen shows.
"""

import time

#: Each module's picture against the room inside its cell, in the desk's own
#: pixels: where the picture is drawn, which is centered in its box at its own
#: size, and where the cell's edge leaves off. The sizes are read off the
#: pictures themselves rather than written here.
CELLS = """
const done = arguments[arguments.length - 1];
const window_ = document.querySelector("nx-window[name=preferences]");
const zoom = Number(getComputedStyle(document.body).zoom) || 1;
const band = window_.querySelector("nx-scroller.modules").view;
Promise.all([...window_.querySelectorAll(".module")].map(async (cell) => {
  const art = cell.querySelector(".art");
  const picture = new Image();
  picture.src = getComputedStyle(art).backgroundImage.slice(5, -2);
  await picture.decode();
  const outer = cell.getBoundingClientRect();
  const box = art.getBoundingClientRect();
  const left = outer.left / zoom + cell.clientLeft;
  const top = outer.top / zoom + cell.clientTop;
  const middleX = (box.left + box.width / 2) / zoom;
  const middleY = (box.top + box.height / 2) / zoom;
  return {
    module: cell.getAttribute("value"),
    room: [left, top, left + cell.clientWidth, top + cell.clientHeight],
    drawn: [middleX - picture.width / 2, middleY - picture.height / 2,
            middleX + picture.width / 2, middleY + picture.height / 2],
  };
})).then((cells) => done({ cells, over: band.scrollHeight - band.clientHeight }));
"""

#: Less than this is a rounding of a fractional desk size, not a pixel lost.
ROUNDING = 0.01


def test_every_module_picture_shows_whole_inside_its_cell(desk):
    """Monitor's picture is 66 by 57, and Localization's 52 by 49. Each sits
    inside its cell's edge with nothing cut, and the row of cells fits the band
    it is drawn in."""
    desk.execute_script("document.querySelector('nx-window[name=preferences]').open()")
    time.sleep(0.6)
    measured = desk.execute_async_script(CELLS)

    for cell in measured["cells"]:
        left, top, right, bottom = cell["room"]
        drawn_left, drawn_top, drawn_right, drawn_bottom = cell["drawn"]
        assert drawn_left >= left - ROUNDING, "%s is cut on its left" % cell["module"]
        assert drawn_top >= top - ROUNDING, "%s is cut along its top" % cell["module"]
        assert drawn_right <= right + ROUNDING, "%s is cut on its right" % cell["module"]
        assert drawn_bottom <= bottom + ROUNDING, "%s is cut along its foot" % cell["module"]
    assert measured["over"] <= 0, "the row runs %d past its band" % measured["over"]
