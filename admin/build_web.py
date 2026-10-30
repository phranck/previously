#!/usr/bin/env python3
"""Puts the interface together as the thing a browser is given.

    python3 build_web.py [--into DIRECTORY]

`interface/` is where the interface is written: one file per subject, with the
comments that say why each of them is the way it is. `web/` is what ships, and
nothing in it is written by hand: one script, one stylesheet, a markup with no
comments in it, one catalog per language the script does not carry, and the
assets that are already files.

The two are kept apart because they are for different readers. A comment in
this project is a paragraph about a decision, and it belongs in the source and
nowhere near the requests a browser makes to draw the desk.

esbuild does the minifying, and node reads the catalogs. Stripping comments out
of JavaScript by hand means knowing where a string ends, where a template
literal ends and where a regular expression begins, and a mistake in that is a
page that does not load. Both are needed here and on whatever runs the tests,
and never on the Pi: what this writes is committed, so a package built from a
checkout carries the same files as the published one.
"""

import argparse
import json
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
SOURCE = HERE / "interface"
SERVED = HERE / "web"

#: Where the interface starts. Everything else it is made of, the kit, the
#: English catalog and this application's own modules, is reached from here
#: through imports, so the order a browser runs them in is written in the code
#: that needs them rather than in a list over here that has to agree with it.
ENTRY = "app.js"

#: The folder the catalogs are in, one per language, in `interface/` and in
#: `web/` alike. The script carries the ones it imports, which is English, and
#: every other one is written into this folder of `web/` as a file of its own,
#: which the page fetches when its language is the one chosen. `strings.js`
#: names the same folder, and the page's tests answer from what this writes,
#: which is what holds the two to each other.
CATALOGS = "lang"

#: What reads the catalogs the way the page reads English, by importing them,
#: and says every one it was given back as one JSON object keyed by language.
#: A catalog is JavaScript with comments in it, so node reads it rather than a
#: pattern written here, for the reason above. Each catalog exports its table
#: under the code of its language, `de.js` as `de`.
READ_CATALOGS = """
import { basename } from "node:path";
import { pathToFileURL } from "node:url";

const read = {};
for (const file of process.argv.slice(1)) {
  const language = basename(file, ".js");
  read[language] = (await import(pathToFileURL(file).href))[language];
}
process.stdout.write(JSON.stringify(read));
"""

#: Each tool the build runs, and how to put it on a machine that lacks it.
TOOLS = {
    "esbuild": "brew install esbuild, or npm install --global esbuild",
    "node": "install the version ../.nvmrc names, such as with brew install node",
}

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


def need(tool):
    """Stops the build where a tool it runs is not on this machine.

    @param tool - One of TOOLS, which says how to install it.
    """
    if shutil.which(tool) is None:
        raise SystemExit("%s is not here: %s" % (tool, TOOLS[tool]))


def minified(text, loader):
    """@param text - What to minify.
    @param loader - "js" or "css", which is what esbuild calls the two.
    @returns str

    Legal comments are kept and moved to the foot, so the license the vendor
    stylesheet carries survives being bundled with everything else.
    """
    need("esbuild")
    answer = subprocess.run(
        ["esbuild", "--minify", "--legal-comments=eof",
         "--charset=utf8", "--loader=" + loader],
        input=text, capture_output=True, text=True, check=True)
    return answer.stdout


def script():
    """@returns tuple of the interface bundled from its one entry, minified, as
      str, and the set of every source file in it, as resolved pathlib.Path.

    esbuild follows the imports, so the order the browser runs things in is
    the order the modules ask for each other rather than a list kept here.
    What comes out is one function with nothing in it reaching the page:
    nothing outside needs any of these names, because the elements define
    themselves, the listeners are added in code, and the markup carries no
    handler of its own.

    The set is esbuild's own account of where the imports led, out of its
    metafile, whose paths are relative to the directory it ran in. `catalogs`
    reads it to know which catalogs the script carries already. esbuild writes
    a metafile only beside a bundle it writes into a file, so both go into a
    scratch directory and are read back from there.

    `tsconfig.json` beside the sources is the type checker's, and esbuild reads
    it unless told otherwise. Its `strict` would put a "use strict" in front of
    the bundle, which changes nothing in code made of modules, so the build is
    given an empty one and ships the same whatever the checker is set to.
    """
    need("esbuild")
    with tempfile.TemporaryDirectory() as scratch:
        bundle = pathlib.Path(scratch) / BUNDLE_JS
        metafile = pathlib.Path(scratch) / "meta.json"
        subprocess.run(
            ["esbuild", str(SOURCE / ENTRY), "--bundle", "--minify",
             "--format=iife", "--legal-comments=eof", "--charset=utf8",
             "--tsconfig-raw={}", "--log-level=warning",
             "--outfile=" + str(bundle), "--metafile=" + str(metafile)],
            cwd=HERE, check=True)
        inputs = json.loads(metafile.read_text(encoding="utf-8"))["inputs"]
        return (bundle.read_text(encoding="utf-8"),
                {(HERE / name).resolve() for name in inputs})


def catalogs(bundled):
    """Every catalog the script does not carry, as the file the page fetches.

    @param bundled - set of the source files in the script, as `script`
      returns it.
    @returns dict of each catalog's name in `web/`, such as `lang/de.json`, to
      its table as one line of JSON.

    The script carries English, because `strings.js` imports it, and esbuild
    says so. Every other language is written here, so a browser holds English
    and the one language it is reading, and the rest stay on the Pi.
    """
    need("node")
    wanted = [path for path in sorted((SOURCE / CATALOGS).glob("*.js"))
              if path.resolve() not in bundled]
    answer = subprocess.run(
        ["node", "--input-type=module", "--eval", READ_CATALOGS,
         *(str(path) for path in wanted)],
        capture_output=True, text=True, check=True)
    read = json.loads(answer.stdout)
    return {"%s/%s.json" % (CATALOGS, path.stem):
            json.dumps(read[path.stem], ensure_ascii=False, separators=(",", ":"))
            for path in wanted}


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
    """Writes the three files, and the catalogs the script does not carry.

    @param into - pathlib.Path of the directory that is served, which the test
      hands a temporary one so it can compare what comes out with what is
      committed.
    @returns dict of each file's name in `into`, such as `previously.js` or
      `lang/de.json`, to what was written there.

    The catalogs' folder is emptied first, because everything in it is written
    here, and a catalog that has gone into the script would otherwise stay
    behind as a file nothing asks for.
    """
    bundle, bundled = script()
    written = {"index.html": markup(), BUNDLE_JS: bundle,
               BUNDLE_CSS: stylesheet(), **catalogs(bundled)}
    if (into / CATALOGS).exists():
        shutil.rmtree(into / CATALOGS)
    for name, text in written.items():
        target = into / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
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
