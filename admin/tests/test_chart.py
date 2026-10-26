"""The lamps of a chart sit on whole device pixels at every size.

The interface is drawn at 100 to 200 per cent in steps of 25, and read on
displays of two device pixels per pixel. A lamp or a gap that comes out at half
a device pixel is rounded differently along a row of a chart, and the last
columns run together, which happened with lamps of three pixels and gaps of
one. A layout cannot be measured without a browser, so what this holds is the
cause: every length the chart's grid is built from.
"""

import re

import pytest

from conftest import INTERFACE

#: The chart's own stylesheet in the kit.
CHART_CSS = INTERFACE.parent.parent / "design" / "kit" / "chart.css"

#: The sizes the interface offers, as interface/app/size.js lists them.
SIZES = (1, 1.25, 1.5, 1.75, 2)

#: Device pixels per pixel on the displays this is read on.
DENSITY = 2

#: The properties a chart's grid is built from.
GRID = ("gap", "width", "height")


def grid_lengths(css):
    """@returns dict from `selector property` to its length in pixels, for
    every grid property of a rule about nx-chart's columns, lamps or field."""
    found = {}
    for selector, body in re.findall(r"(nx-chart \.[\w-]+)\s*\{([^}]*)\}", css):
        for prop, value in re.findall(r"(?m)^\s*([\w-]+):\s*(\d+(?:\.\d+)?)px;", body):
            if prop in GRID:
                found["%s %s" % (selector, prop)] = float(value)
    return found


def on_half_pixels(lengths):
    """@returns list of the lengths that land on a fraction of a device pixel
    at some size."""
    return sorted("%s at %d%%" % (name, size * 100)
                  for name, length in lengths.items() for size in SIZES
                  if (length * size * DENSITY) % 1)


def test_the_grid_is_stated():
    lengths = grid_lengths(CHART_CSS.read_text(encoding="utf-8"))

    assert {"nx-chart .field gap", "nx-chart .column gap", "nx-chart .column width",
            "nx-chart .led height"} <= set(lengths)


#: Every stylesheet the page is drawn with apart from the chart's own.
STYLESHEETS = [path for path in (INTERFACE.parent.parent / "design" / "kit").glob("*.css")
               if path.name != "chart.css"] + [INTERFACE / "app.css"]

#: The class a chart gives its lamps, as chart.js writes it.
CHART_JS = CHART_CSS.with_suffix(".js")


def rules_for(name, css):
    """@returns list of the selectors in a stylesheet that would style an
    element of that class wherever it stands, without an ancestor to keep it
    to its own element."""
    pattern = r"(?m)(?:^|[,}])\s*(\." + re.escape(name) + r")\b[^{]*[,{]"
    return re.findall(pattern, css)


def test_nothing_else_styles_a_chart_lamp():
    """A chart's lamps once wore `lamp`, the class of the lamp beside a state:
    nine pixels with a border, which spilled over the neighbors and ran the
    columns together."""
    written = CHART_JS.read_text(encoding="utf-8")
    name = re.search(r'led\.className = "([\w-]+)"', written).group(1)

    clashes = [path.name for path in STYLESHEETS
               if rules_for(name, path.read_text(encoding="utf-8"))]

    assert clashes == []


def test_the_class_that_clashed_is_caught():
    """So this test is known to see the clash it guards against."""
    assert rules_for("lamp", (INTERFACE.parent.parent / "design" / "kit" / "panel.css")
                     .read_text(encoding="utf-8"))


def test_every_length_of_the_grid_is_whole_device_pixels_at_every_size():
    lengths = grid_lengths(CHART_CSS.read_text(encoding="utf-8"))

    assert on_half_pixels(lengths) == []


@pytest.mark.parametrize("lamp, gap", [(3, 1)])
def test_lamps_of_three_with_gaps_of_one_are_caught(lamp, gap):
    """The grid that ran together, so this test is known to see it."""
    css = ("nx-chart .field {\n  gap: %dpx;\n}\nnx-chart .column {\n  gap: %dpx;\n"
           "  width: %dpx;\n}\n" % (gap, gap, lamp))

    assert on_half_pixels(grid_lengths(css)) != []
