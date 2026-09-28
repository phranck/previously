#!/usr/bin/env python3
"""Puts the interface together as the thing a browser is given.

    python3 build_web.py [--into DIRECTORY]

`interface/` is where the interface is written: one file per subject, with the
comments that say why each of them is the way it is. `web/` is what ships, and
nothing in it is written by hand: one script, one stylesheet, a markup with no
comments in it, and the assets that are already files.

The two are kept apart because they are for different readers. A comment in
this project is a paragraph about a decision, and it belongs in the source and
nowhere near the fourteen requests a browser used to make to draw the desk.

esbuild does the minifying. Stripping comments out of JavaScript by hand means
knowing where a string ends, where a template literal ends and where a regular
expression begins, and a mistake in that is a page that does not load. It is
needed here and on whatever runs the tests, and never on the Pi: what this
writes is committed, so a package built from a checkout carries the same files
as the published one.
"""

import argparse
import pathlib
import re
import shutil
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
SOURCE = HERE / "interface"
SERVED = HERE / "web"

#: The scripts, in the order a browser runs them. The words first, so every
#: element is built around text it already has; then the kit, which defines the
#: elements; then this application. `translate()` stands between the catalogues
#: and the kit, where the markup used to carry it inline.
SCRIPTS = ("strings.js", "lang/en.js", "lang/de.js", "lang/fr.js",
           "lang/it.js", "lang/es.js", "lang/sv.js", "translate();",
           "nextstep.js", "terminal.js", "app.js")

#: The stylesheets, in the order they cascade.
STYLES = ("vendor/xterm.css", "nextstep.css", "app.css")

#: What the browser is given. The vendor library keeps its own tag: it arrives
#: minified from the people who wrote it, it is a third of a megabyte, and it
#: never changes, so putting it in a file that is rewritten on every edit would
#: cost a great deal and save one request on a local network.
BUNDLE_JS = "previously.js"
BUNDLE_CSS = "previously.css"
VENDOR_SCRIPTS = ("vendor/xterm.js", "vendor/xterm-addon-fit.js")

#: Where the page says so. Written into the markup rather than left implicit,
#: because somebody reading the source of a page deserves to know that what
#: they are looking at was built and where it was built from.
SAYS = ("<!-- Built by admin/build_web.py from admin/interface/. "
        "The sources are in the repository. -->")


def minified(text, loader):
    """@param text - What to minify.
    @param loader - "js" or "css", which is what esbuild calls the two.
    @returns str

    Legal comments are kept and moved to the foot, so the licence the vendor
    stylesheet carries survives being bundled with everything else.
    """
    if shutil.which("esbuild") is None:
        raise SystemExit("esbuild is not here: brew install esbuild, or "
                         "npm install --global esbuild")
    answer = subprocess.run(
        ["esbuild", "--minify", "--legal-comments=eof",
         "--charset=utf8", "--loader=" + loader],
        input=text, capture_output=True, text=True, check=True)
    return answer.stdout


def script():
    """@returns str, every script of ours as one, private and minified.

    Wrapped in a function, so that nothing in it is a global and esbuild can
    shorten every name in it. Nothing outside needs any of them: the elements
    register themselves, the listeners are added in code, and the markup
    carries no handler of its own.
    """
    written = []
    for name in SCRIPTS:
        if name.endswith(";"):
            written.append(name)
            continue
        written.append((SOURCE / name).read_text(encoding="utf-8"))
    return minified("(() => {\n%s\n})();\n" % "\n".join(written), "js")


def stylesheet():
    """@returns str, every stylesheet as one, minified."""
    written = [(SOURCE / name).read_text(encoding="utf-8") for name in STYLES]
    return minified("\n".join(written), "css")


def markup():
    """@returns str, the page with its comments gone and three tags for fourteen.

    The comments in the source say why the markup is the way it is, which is a
    question for whoever edits it rather than for whoever loads it.
    """
    text = (SOURCE / "index.html").read_text(encoding="utf-8")
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)

    links = '<link rel="stylesheet" href="%s">' % BUNDLE_CSS
    scripts = "\n".join(
        ['<script src="%s"></script>' % name for name in VENDOR_SCRIPTS]
        + ['<script src="%s"></script>' % BUNDLE_JS])

    text = one_instead_of_many(text, r'[ \t]*<link rel="stylesheet"[^>]*>\n',
                               links + "\n", "stylesheet")
    text = one_instead_of_many(text, r"[ \t]*<script\b.*?</script>\n",
                               scripts + "\n", "script")

    # What removing a comment leaves behind, and the blank line the source uses
    # between two things that belong apart. Two in a row is the most a document
    # needs; anything beyond that was a paragraph of prose a moment ago.
    text = re.sub(r"[ \t]+$", "", text, flags=re.M)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.replace("<body>", "<body>\n\n" + SAYS, 1)


def one_instead_of_many(text, pattern, replacement, what):
    """Puts one tag where a run of them stood.

    @param text - The markup.
    @param pattern - What matches one of the tags being replaced.
    @param replacement - What goes where the first of them was.
    @param what - The name of the kind, for the complaint.
    @returns str

    In the first one's place rather than the last one's, because these are in
    the order they are loaded in and the order is what makes the page work.
    """
    found = list(re.finditer(pattern, text, flags=re.DOTALL))
    if not found:
        raise SystemExit("no %s tag in index.html" % what)
    first = found[0].start()
    for match in reversed(found):
        text = text[:match.start()] + text[match.end():]
    return text[:first] + replacement + text[first:]


def build(into=SERVED):
    """Writes the three files.

    @param into - pathlib.Path of the directory that is served, which the test
      hands a temporary one so it can compare what comes out with what is
      committed.
    @returns dict of name to what was written.
    """
    written = {"index.html": markup(), BUNDLE_JS: script(),
               BUNDLE_CSS: stylesheet()}
    into.mkdir(parents=True, exist_ok=True)
    for name, text in written.items():
        (into / name).write_text(text, encoding="utf-8")
    return written


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--into", default=str(SERVED),
                        help="where the browser's files go")
    written = build(pathlib.Path(parser.parse_args().into))
    print("wrote %s" % ", ".join(
        "%s (%d kB)" % (name, round(len(text.encode("utf-8")) / 1024))
        for name, text in written.items()))


if __name__ == "__main__":
    sys.exit(main())
