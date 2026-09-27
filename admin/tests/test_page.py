"""The page and the markup, held against each other.

`app.js` fills the interface in by name: it asks for an element by its id and
writes into it. A name that is not in `index.html` answers nothing, and what
follows is a page that throws where somebody clicked rather than at a start, in
whichever window that line belongs to. Reading both files is what catches it, and
no browser has to be opened to do that.
"""

import re

import pytest

from previously.server import WEB_ROOT

#: How the page reaches an element. getElementById is the plain way, and the rest
#: are this page's own helpers, which take an id and write into it.
BY_ID = re.compile(
    r'(?:getElementById|show|explain|fillWithChoices|drawPicture)\(\s*"([^"]+)"')

#: What the markup calls its elements.
IN_MARKUP = re.compile(r'\bid="([^"]+)"')

#: A window or a menu the page asks for by name, which the kit builds from the
#: markup and which answers nothing where the markup has no such thing.
BY_NAME = re.compile(r'nx-(?:window|menu|menu-item|tile)\[name="([^"]+)"\]')

#: What the editor reads off one entry of `offers.kinds`. That group is the one
#: place a cell takes its label from the service instead of from this page's own
#: words, because a machine type is named by the emulator.
FROM_A_KIND = re.compile(r"\bkind\.(\w+)")

#: Which subject each of the editor's groups belongs to, and the subjects the
#: page offers to choose between. The window shows one subject at a time, so the
#: two lists have to be the same one.
A_GROUP_S_SUBJECT = re.compile(r'\bsubject="([^"]+)"')
THE_SUBJECTS = re.compile(r'^  (\w+): "editor\.subject\.\w+",$', re.M)


@pytest.fixture(scope="module")
def page():
    return (WEB_ROOT / "app.js").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def markup():
    return (WEB_ROOT / "index.html").read_text(encoding="utf-8")


def test_every_element_the_page_writes_into_is_in_the_markup(page, markup):
    wanted = set(BY_ID.findall(page))
    have = set(IN_MARKUP.findall(markup))

    assert sorted(wanted - have) == []


def test_every_window_and_entry_the_page_reaches_for_exists(page, markup):
    """Reached by name rather than by id, because that is what the kit remembers
    a window by and what a menu entry says it belongs to.

    Only the ones written out. A name the page builds from a value is whatever
    the service sent, and the one list of those is an application's `opens`,
    which the test below holds to the markup.
    """
    wanted = {name for name in BY_NAME.findall(page) if "${" not in name}
    have = set(re.findall(r'\bname="([^"]+)"', markup))

    assert sorted(wanted - have) == []


def test_every_application_opens_a_window_that_is_there(markup):
    """An application in the tree says which window it opens, and the page opens
    that one when its icon is double clicked. One naming a window the markup does
    not hold is an icon that answers with a panel saying it does not exist yet,
    which is the right answer for an application nobody has built and the wrong
    one for a typing mistake."""
    from previously import files

    windows = set(re.findall(r'<nx-window name="([^"]+)"', markup))
    opens = {opens for _, _, opens, _ in files.APPLICATIONS}

    assert sorted(opens - windows) == []


def test_the_page_asks_for_something(page, markup):
    """Both tests above pass on an empty set, so this is what says they were
    measuring anything at all."""
    assert len(set(BY_ID.findall(page))) > 20
    assert len(set(BY_NAME.findall(page))) > 5


def test_the_editor_reads_what_a_machine_type_actually_carries(page):
    """A cell in the machine type group is labelled with one field of an entry
    and marked as chosen by another, so an entry carrying neither draws a row of
    buttons with nothing written in them and nothing chosen."""
    from previously import machines

    wanted = set(FROM_A_KIND.findall(page))
    have = set(machines.offers(machines.find("nextcube"))["kinds"][0])

    assert wanted
    assert sorted(wanted - have) == []


def test_every_subject_the_editor_offers_has_groups_to_show(page, markup):
    """The window shows one subject at a time, so one that no group belongs to
    is a cell that empties the window, and a group belonging to a subject the row
    does not offer is a group nobody can reach."""
    offered = set(THE_SUBJECTS.findall(page))
    in_markup = set(A_GROUP_S_SUBJECT.findall(markup))

    assert offered
    assert offered == in_markup


def test_every_group_in_the_editor_belongs_to_a_subject(markup):
    """One that belongs to none is shown whatever is chosen, so it turns up
    under every subject."""
    editor = markup[markup.index('<div class="editor-groups">'):]
    editor = editor[:editor.index("</div>\n  <p class=\"note\"")]
    groups = re.findall(
        r'<(?:fieldset|div)[^>]*class="[^"]*\b(?:group|boards-memory)\b[^"]*"[^>]*>',
        editor)

    assert len(groups) > 8
    assert [group for group in groups if "subject=" not in group] == []
