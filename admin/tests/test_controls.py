"""The switch and the radio button are what design/controls.py cuts.

They come out of two grabs of the running system, and a picture edited by hand
is a change the next run throws away without saying so. This is what says so.
"""

import importlib.util

import pytest
from PIL import ImageChops, Image

from conftest import INTERFACE

#: The tool, loaded from where it lives rather than installed. It writes
#: nothing when it is imported.
CUTTER = INTERFACE.parent.parent / "design" / "controls.py"


@pytest.fixture(scope="module")
def controls():
    spec = importlib.util.spec_from_file_location("controls", CUTTER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("name", ["switch", "switch-on", "radio", "radio-on"])
def test_each_control_is_what_the_cutter_cuts(controls, name):
    served = Image.open(controls.path(name)).convert("RGB")

    assert served.size == (15, 15)
    assert ImageChops.difference(served, controls.cut(name)).getbbox() is None, \
        "run design/controls.py"
