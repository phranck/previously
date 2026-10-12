"""Every type the interface writes down checks something.

`tsc` reads the documentation comments and the declaration files under the
strict rules, so a value with no type of its own is refused. What those rules
let through is a type written as `any`, which turns the checking off for that
value and for everything it is handed to, and a comment telling the checker to
look away. Both are refused here, in the interface and in the kit's sources.
"""

import re

from conftest import INTERFACE

#: The kit's sources, which interface/nextstep.js is put together from.
KIT = INTERFACE.parent.parent / "design" / "kit"

#: A documentation comment naming a type, up to the brace the type opens with.
A_TYPE = re.compile(
    r"@(?:type|param|returns?|property|prop|typedef|template|satisfies|this|throws)\s*\{")

#: A type that checks nothing: TypeScript's own, and JSDoc's two ways of
#: writing it.
UNCHECKED = re.compile(r"\bany\b|^\s*[*?]\s*$")

#: A comment that switches the checker off for what follows it.
LOOKING_AWAY = re.compile(r"@ts-(?:ignore|nocheck|expect-error)")

#: A comment in a declaration file, whose prose may say "any" as a word.
A_COMMENT = re.compile(r"/\*.*?\*/|//[^\n]*", re.S)


def sources():
    """@returns list of pathlib.Path - Everything the checker reads, without the
    vendored library, which is typed by its own release."""
    written = [path for path in sorted(INTERFACE.rglob("*.js"))
               if "vendor" not in path.relative_to(INTERFACE).parts]
    return [*written, *sorted(INTERFACE.glob("*.d.ts")), *sorted(KIT.glob("*.js"))]


def written_types(text):
    """Every type a documentation comment names.

    @param text - A JavaScript source.
    @returns list of str - What stands between each type's braces, read to the
      brace that closes it, so a type holding an object type is read whole.
    """
    found = []
    for opening in A_TYPE.finditer(text):
        depth, at = 1, opening.end()
        while depth and at < len(text):
            depth += {"{": 1, "}": -1}.get(text[at], 0)
            at += 1
        found.append(text[opening.end():at - 1])
    return found


def unchecked_in(path):
    """@param path - One source.
    @returns list of str - Each type in it that checks nothing, and each comment
      that tells the checker to look away."""
    text = path.read_text(encoding="utf-8")
    if path.name.endswith(".d.ts"):
        types = A_COMMENT.sub("", text).splitlines()
    else:
        types = written_types(text)
    return ([f"{path.name}: {{{kind.strip()}}}" for kind in types if UNCHECKED.search(kind)]
            + [f"{path.name}: {line.strip()}" for line in text.splitlines()
               if LOOKING_AWAY.search(line)])


def test_no_type_is_any():
    unchecked = [found for path in sources() for found in unchecked_in(path)]

    assert unchecked == []


def test_the_types_are_read():
    """The test above passes on nothing, so this is what says it read the types
    the interface writes down."""
    types = [kind for path in sources() if path.suffix == ".js"
             for kind in written_types(path.read_text(encoding="utf-8"))]

    assert len(types) > 500
    assert {"string", "boolean", "number"} <= set(types)
