"""The files the interface is built and checked from are the kit, put together.

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


def test_the_tag_map_is_what_the_kit_says(build):
    """Which tag is which element, for the type checker. A tag the kit defines
    that is missing here is one `querySelector` answers as a bare Element."""
    served = (INTERFACE / "elements.d.ts").read_text(encoding="utf-8")

    assert served == build.elements(), "run design/build.py"


#: A picture the kit's stylesheet points at, by the name of its file.
NAMED_PICTURE = re.compile(r'url\("parts/([^"]+)"\)')


def test_every_picture_the_kit_names_is_served(build):
    """The kit names its pictures by hand, and the admin serves them from
    web/parts. A name with no file there is an icon that never appears and a
    404 on every load, and nothing else in the suite would notice."""
    named = NAMED_PICTURE.findall(build.stylesheet())
    assert len(named) > 20, "the stylesheet names no pictures this can read"

    missing = [name for name in named if not (build.PARTS / name).is_file()]
    assert missing == []


#: A face a stylesheet ships, by the family its `@font-face` rule gives it.
SHIPPED_FAMILY = re.compile(r'@font-face\s*\{[^}]*font-family:\s*"([^"]+)"', re.S)

#: A `@font-face` rule, which names the family it ships rather than one a rule
#: draws in.
FONT_FACE_RULE = re.compile(r"@font-face\s*\{[^}]*\}", re.S)

#: Where a rule sets a face: a `font` shorthand or a `font-family`. The
#: lookbehind keeps out a custom property such as `--font`, which is a token
#: rather than a rule.
SETS_A_FACE = re.compile(r"(?<![\w-])font(-family)?\s*:\s*([^;}]+)")

#: A custom property and its value, as the stylesheets declare them.
TOKEN = re.compile(r"(--[\w-]+)\s*:\s*([^;}]+)")

#: A whole value that is one custom property and nothing else.
ONE_TOKEN = re.compile(r"var\((--[\w-]+)\)")


def stylesheets(build):
    """@returns the kit's stylesheet and this interface's own, without comments."""
    both = build.stylesheet() + (INTERFACE / "app.css").read_text(encoding="utf-8")
    return re.sub(r"/\*.*?\*/", "", both, flags=re.S)


def families(shorthand, value):
    """The list of families a declaration sets, or None where it sets none.

    @param shorthand - True for `font`, False for `font-family`.
    @param value - What the declaration says.
    @returns str or None.

    The `font` shorthand ends in the families and states a size before them,
    so they are what follows the first word that is a size. A shorthand with
    no size, such as `font: inherit`, takes the face from elsewhere.
    """
    if not shorthand:
        return value.strip()
    words = value.split()
    for index, word in enumerate(words):
        if re.search(r"\d|var\(", word):
            return " ".join(words[index + 1:])
    return None


def first_family(listed, tokens):
    """@returns the family a list draws in, following a token to its value."""
    first = listed.split(",")[0].strip()
    while (token := ONE_TOKEN.fullmatch(first)):
        first = tokens[token.group(1)].split(",")[0].strip()
    return first.strip('"')


def test_every_face_the_interface_draws_in_is_one_it_ships(build):
    """A face named from the machine, such as Helvetica, is a different face on
    every machine, and Arial or a browser's own sans stands in where there is
    none. So the face a rule draws in, the first of its list, is one the
    stylesheets ship themselves. What follows it in the list is there for a
    file that failed to load."""
    css = stylesheets(build)
    shipped = set(SHIPPED_FAMILY.findall(css))
    assert "Inconsolata" in shipped, "the stylesheets ship no face this can read"
    tokens = dict(TOKEN.findall(css))

    drawn = set()
    for prefix, value in SETS_A_FACE.findall(FONT_FACE_RULE.sub("", css)):
        listed = families(not prefix, value)
        if listed:
            drawn.add(first_family(listed, tokens))
    assert len(drawn) > 1, "no rule sets a face this can read"

    assert sorted(drawn - shipped) == []


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
    dock = re.search(r"<nx-dock\b[^>]*>(.*?)</nx-dock>", markup, re.S)
    assert dock, "the dock is not in the markup"

    for tile in re.findall(r"<nx-tile\b[^>]*>", dock.group(1), re.S):
        if re.search(r"\bfixed\b", tile):
            continue
        assert re.search(r'\bname="[^"]+"', tile), tile
