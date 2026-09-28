"""The two files the interface is built from are the kit, put together.

They are generated, and a generated file that somebody edits by hand is a
change that the next build throws away without saying so. This is what says
so, and it is the reason the kit can be one source again: the copies cannot
drift, because a drifted copy fails here.
"""

import importlib.util
import re

import pytest

from conftest import INTERFACE

#: The builder, loaded from where it lives rather than installed. It writes
#: nothing when it is imported.
BUILDER = INTERFACE.parent.parent / "design" / "build.py"


@pytest.fixture(scope="module")
def build():
    spec = importlib.util.spec_from_file_location("build", BUILDER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_builder_is_where_the_tests_look_for_it():
    assert BUILDER.is_file()


def test_the_stylesheet_is_what_the_kit_says(build):
    served = (INTERFACE / "nextstep.css").read_text(encoding="utf-8")

    assert served == build.stylesheet(), "run design/build.py"


def test_the_script_is_what_the_kit_says(build):
    served = (INTERFACE / "nextstep.js").read_text(encoding="utf-8")

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


#: What the kit's own scripts build, by the class they put on it. Those are the
#: kit's inner structure rather than names an interface is meant to use.
BUILT_BY_THE_KIT = re.compile(r'class(?:Name)?\s*=\s*"([a-z][a-z0-9 -]*)"')

#: The first thing a rule matches on, which is what decides whether it reaches
#: into somebody else's element or only into its own.
FIRST_OF_A_SELECTOR = re.compile(r"^\s*([.#\w\[][^\s,{>+~]*)", re.M)


def kit_classes():
    """@returns set of every class the kit's scripts put on an element."""
    found = set()
    for source in (INTERFACE.parent.parent / "design" / "kit").glob("*.js"):
        for names in BUILT_BY_THE_KIT.findall(source.read_text(encoding="utf-8")):
            found.update(names.split())
    return found


def test_the_kit_builds_things_this_can_name():
    """Both tests below pass on an empty set, so this is what says they were
    measuring anything at all."""
    assert len(kit_classes()) > 10
    assert "panel" in kit_classes()


def test_this_interface_names_nothing_the_kit_builds(build):
    """A bare rule for a class the kit puts on its own elements reaches inside
    them. `.panel { padding: 10px }` here, meant for one module of Preferences,
    moved the attention panel's title bar thirteen pixels off its frame, and
    nothing in either file said the two were the same name.

    Only where the rule begins with it. `.module .art` is this interface
    reaching into its own module, which is its business.
    """
    ours = (INTERFACE / "app.css").read_text(encoding="utf-8")
    # The rules alone, so a class named inside a comment or a value is not read
    # as a selector.
    ours = re.sub(r"/\*.*?\*/", "", ours, flags=re.S)

    theirs = kit_classes()
    reaching = set()
    for block in ours.split("}"):
        selector = block.split("{")[0]
        if not selector.strip():
            continue
        for first in FIRST_OF_A_SELECTOR.findall(selector):
            if first.startswith(".") and first[1:] in theirs:
                reaching.add(first)

    assert sorted(reaching) == []


def test_a_tile_that_can_be_carried_carries_a_name():
    """The dock remembers where a tile was put under that tile's name, so one
    without a name goes back to where the markup has it at every reload, and
    nothing says why."""
    markup = (INTERFACE / "index.html").read_text(encoding="utf-8")
    dock = re.search(r"<nx-dock>(.*?)</nx-dock>", markup, re.S)
    assert dock, "the dock is not in the markup"

    for tile in re.findall(r"<nx-tile\b[^>]*>", dock.group(1), re.S):
        if re.search(r"\bfixed\b", tile):
            continue
        assert re.search(r'\bname="[^"]+"', tile), tile
