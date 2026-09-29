"""What release notes turn into, run rather than read.

`markdown.js` imports nothing of ours and touches six things a document can do,
so node runs it against `markdown_page.mjs` and this reads the tree that comes
out. That matters most for the two things a reader cannot check by eye: a line
carrying something that looks like markup, and a link leading somewhere a
document should not lead.

The tree is written as indented lines rather than as markup, because a test that
compared markup would be a test that built markup, which is the one thing the
renderer is built not to do.
"""

import pathlib
import shutil
import subprocess

import pytest

#: The little page that lets node run the renderer.
PAGE = pathlib.Path(__file__).resolve().parent / "markdown_page.mjs"


def rendered(notes):
    """@returns str - The tree those notes become, one node per line."""
    if shutil.which("node") is None:
        pytest.skip("node is not on this machine")

    answer = subprocess.run(
        ["node", str(PAGE)], input=notes, capture_output=True, text=True,
        timeout=30, check=False)
    assert answer.returncode == 0, answer.stderr
    return answer.stdout


def elements(tree):
    """@returns set - Every kind of element in that tree, by its name.

    A line is either an element or a piece of text, and the text says so. So
    what is left is what the renderer created, which is what a test about markup
    reaching a page has to be able to ask about.
    """
    return {line.strip().split(" ", 1)[0] for line in tree.splitlines()
            if line.strip() and not line.strip().startswith("text ")}


# -- what the notes actually use ------------------------------------------


def test_a_heading_is_as_deep_as_its_hashes():
    tree = rendered("# One\n\n## Two\n\n### Three\n")

    assert "h1" in tree and "h2" in tree and "h3" in tree
    assert 'text "One"' in tree


def test_a_paragraph_is_joined_into_one_line():
    """Markdown wraps a paragraph wherever it was typed, and a window is a
    different width from whatever that was."""
    tree = rendered("It brings its own units,\nand takes them out again.\n")

    assert 'text "It brings its own units, and takes them out again."' in tree


def test_a_fenced_block_keeps_its_lines():
    """Which is what a fence is for. A command run together with the next one
    is a command somebody would copy wrongly."""
    tree = rendered("```bash\nsudo apt install ./x.deb\ncd /tmp\n```\n")

    assert 'pre language="bash"' in tree
    assert '"sudo apt install ./x.deb\\ncd /tmp"' in tree


def test_a_run_of_items_is_one_list():
    tree = rendered("- one\n- two\n- three\n").splitlines()

    assert len([line for line in tree if line.strip().startswith("ul")]) == 1
    assert len([line for line in tree if line.strip().startswith("li")]) == 3


def test_a_numbered_run_is_a_numbered_list():
    tree = rendered("1. one\n2. two\n")

    assert "ol" in tree
    assert "ul" not in tree


def test_code_and_bold_inside_a_line_are_drawn_out():
    tree = rendered("It brings `previously.service`, and **nothing else**.\n")

    assert 'code' in tree and 'text "previously.service"' in tree
    assert 'b' in tree and 'text "nothing else"' in tree


# -- what a document may not do -------------------------------------------


def test_something_that_looks_like_markup_arrives_as_its_own_characters():
    """The notes are text somebody wrote, fetched off a network and put into a
    page. Every piece of them becomes the contents of an element rather than
    part of one, so this is what that looks like from outside."""
    tree = rendered("Then <script>alert(1)</script> happens.\n")

    assert 'text "Then <script>alert(1)</script> happens."' in tree
    # Every line that is not text is an element, and none of them is one of
    # those: what looked like markup is inside a paragraph, not beside it.
    assert elements(tree) == {"#fragment", "p"}


def test_a_link_that_is_https_is_a_link():
    tree = rendered("See [previous.li](https://previous.li/page).\n")

    assert 'a href="https://previous.li/page"' in tree
    assert 'target="_blank"' in tree
    # So nothing on the other side can reach back into this window.
    assert 'rel="noreferrer"' in tree


@pytest.mark.parametrize("address", [
    "javascript:alert(1)",
    "data:text/html,<script>alert(1)</script>",
    "http://previous.li/page",
    "file:///etc/passwd",
    "not an address",
])
def test_a_link_that_is_anything_else_is_not_a_link(address):
    """Shown as the characters it was written with, so what somebody wrote is
    read and nothing on the page leads anywhere unexpected."""
    tree = rendered("See [the page](%s).\n" % address)

    assert "\na " not in tree and not tree.startswith("a ")
    assert "href" not in tree
    assert "the page" in tree


def test_notes_that_are_empty_render_to_nothing():
    """A release that says nothing about itself is still a release, and the
    window says there are none rather than drawing an empty document."""
    assert rendered("").strip() == "#fragment"
