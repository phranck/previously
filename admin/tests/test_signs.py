"""The two signs a notification wears beside the stop sign are what
design/signs.py draws.

They are generated, and a sign edited by hand is a change the next run throws
away without saying so. This is what says so.
"""

import importlib.util

import pytest

from conftest import INTERFACE

#: The tool, loaded from where it lives rather than installed. It writes
#: nothing when it is imported.
DRAWER = INTERFACE.parent.parent / "design" / "signs.py"


@pytest.fixture(scope="module")
def signs():
    spec = importlib.util.spec_from_file_location("signs", DRAWER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("name", ["info", "alert"])
def test_each_sign_is_what_the_drawer_says(signs, name):
    served = signs.path(name).read_text(encoding="utf-8")

    assert served == signs.drawing(name), "run design/signs.py"
