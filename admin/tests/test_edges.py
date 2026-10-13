"""The three edges are what design/edges.py draws, and nothing draws an edge
the way that comes apart.

They are generated from the grays in design/kit/base.css, and a picture edited
by hand is a change the next run throws away without saying so. This is what
says so, and it also fails when the palette has changed and nobody ran the
drawer again.

The edges are pictures because a border and an inset shadow on the same side
of a box come apart in WebKit wherever the desk is drawn at a size that does
not fall on whole device pixels, and the background shows between the two
lines. So no rule in the stylesheets is allowed to put the two on one side.
"""

import importlib.util
import re

import pytest

from conftest import INTERFACE

#: The tool, loaded from where it lives rather than installed. It writes
#: nothing when it is imported.
DRAWER = INTERFACE.parent.parent / "design" / "edges.py"

#: Every stylesheet a person writes: the kit's parts and the application's
#: own. What build.py writes out of them is the same rules again.
STYLESHEETS = sorted((INTERFACE.parent.parent / "design" / "kit").glob("*.css")) + [
    INTERFACE / "app.css"]

#: A rule's selector and its declarations, innermost braces only, so a rule
#: inside a media query is read like any other.
RULE = re.compile(r"([^{}]+)\{([^{}]*)\}")
COMMENT = re.compile(r"/\*.*?\*/", re.S)
SIDES = ("top", "right", "bottom", "left")


def bordered_sides(declarations):
    """@returns set of the sides a rule gives a visible border."""
    sides = set()
    for prop, value in re.findall(r"(border(?:-top|-right|-bottom|-left)?)\s*:\s*([^;]+)",
                                  declarations):
        if re.fullmatch(r"\s*(0|none)\s*", value):
            continue
        side = prop.partition("-")[2]
        sides.update([side] if side else SIDES)
    return sides


def shadowed_sides(declarations):
    """@returns set of the sides a rule draws an inset shadow along."""
    sides = set()
    for value in re.findall(r"box-shadow\s*:\s*([^;]+)", declarations):
        for shadow in value.split(","):
            if "inset" not in shadow:
                continue
            across, down = (float(length) for length in
                            re.findall(r"(?<![\w-])(-?[\d.]+)(?:px)?(?![\w%])", shadow)[:2])
            sides.update(side for side, offset in
                         (("left", across), ("right", -across), ("top", down), ("bottom", -down))
                         if offset > 0)
    return sides


@pytest.fixture(scope="module")
def edges():
    spec = importlib.util.spec_from_file_location("edges", DRAWER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_drawer_is_where_the_tests_look_for_it():
    assert DRAWER.is_file()


@pytest.mark.parametrize("name", ["sunken", "raised", "groove"])
def test_each_edge_is_what_the_drawer_says(edges, name):
    served = edges.path(name).read_text(encoding="utf-8")

    assert served == edges.drawing(name), "run design/edges.py"


def resolved(text, properties):
    """@returns the text with every var() it uses replaced by what the custom
      property holds, as often as it takes for none to be left."""
    for _ in range(10):
        text, count = re.subn(r"var\((--[\w-]+)\)",
                              lambda match: properties.get(match.group(1), ""), text)
        if not count:
            break
    return text


def test_no_rule_puts_a_border_and_an_inset_shadow_on_one_side():
    texts = [COMMENT.sub("", sheet.read_text(encoding="utf-8")) for sheet in STYLESHEETS]
    # A rule can name its border or its shadow through a custom property, so
    # it is read with whatever its var() stands for.
    properties = dict(re.findall(r"(--[\w-]+)\s*:\s*([^;]+);", "\n".join(texts)))
    found = []
    for sheet, text in zip(STYLESHEETS, texts):
        for selector, declarations in RULE.findall(text):
            declarations = resolved(declarations, properties)
            both = bordered_sides(declarations) & shadowed_sides(declarations)
            if both:
                found.append(f"{sheet.name}: {selector.strip()} on {', '.join(sorted(both))}")

    assert found == []
