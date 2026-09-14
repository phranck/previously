"""The two files the browser gets are the kit, put together.

They are generated, and a generated file that somebody edits by hand is a
change that the next build throws away without saying so. This is what says
so, and it is the reason the kit can be one source again: the copies cannot
drift, because a drifted copy fails here.
"""

import importlib.util

import pytest

from previously.server import WEB_ROOT

#: The builder, loaded from where it lives rather than installed. It writes
#: nothing when it is imported.
BUILDER = WEB_ROOT.parent.parent / "design" / "build.py"


@pytest.fixture(scope="module")
def build():
    spec = importlib.util.spec_from_file_location("build", BUILDER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_builder_is_where_the_tests_look_for_it():
    assert BUILDER.is_file()


def test_the_stylesheet_is_what_the_kit_says(build):
    served = (WEB_ROOT / "nextstep.css").read_text(encoding="utf-8")

    assert served == build.stylesheet(), "run design/build.py"


def test_the_script_is_what_the_kit_says(build):
    served = (WEB_ROOT / "nextstep.js").read_text(encoding="utf-8")

    assert served == build.script(), "run design/build.py"


def test_every_part_of_the_kit_has_a_source(build):
    """A part named in the table with neither a stylesheet nor a script is a
    line nobody ever sees fail."""
    for name, _, _ in build.KIT_PARTS:
        assert build.source(name, "css") or build.source(name, "js"), name


def test_every_element_it_defines_is_in_its_own_part(build):
    """The definitions are written from the same table that orders the
    sources, so a class named there has to be in the source named beside it."""
    for name, tags, _ in build.KIT_PARTS:
        script = build.source(name, "js")
        for _, class_name in tags:
            assert f"class {class_name} " in script, (name, class_name)
