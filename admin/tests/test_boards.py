"""The four drawings of a board are what design/boards.py draws.

They are generated, and a drawing edited by hand is a change the next run
throws away without saying so. This is what says so. The website and its film
read board-pi5.svg as well, so what they rely on in it is held here too.
"""

import importlib.util
import re

import pytest

from conftest import INTERFACE

#: The tool, loaded from where it lives rather than installed. It writes
#: nothing when it is imported.
DRAWER = INTERFACE.parent.parent / "design" / "boards.py"


@pytest.fixture(scope="module")
def boards():
    spec = importlib.util.spec_from_file_location("boards", DRAWER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_drawer_is_where_the_tests_look_for_it():
    assert DRAWER.is_file()


@pytest.mark.parametrize("name", ["pi4", "pi5", "cm4", "cm5"])
def test_each_drawing_is_what_the_drawer_says(boards, name):
    served = boards.path(name).read_text(encoding="utf-8")

    assert served == boards.drawing(name), "run design/boards.py"


def test_the_pi_5_carries_the_logo_the_film_takes_out_of_it(boards):
    """previous.li's site/board.py finds the logo by its id and reads its paths
    as plain fill and data pairs, in the order next-logo.svg draws them."""
    drawing = boards.path("pi5").read_text(encoding="utf-8")
    groups = re.findall(r'<g id="next-logo"[^>]*>(.*?)</g>', drawing, re.S)

    assert len(groups) == 1
    paths = re.findall(r'<path fill="(#[0-9a-fA-F]+)" d="([^"]+)"/>', groups[0])
    assert paths == boards.next_logo_paths()
