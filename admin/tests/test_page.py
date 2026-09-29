"""The page and the markup, held against each other.

`app.js` fills the interface in by name: it asks for an element by its id and
writes into it. A name that is not in `index.html` answers nothing, and what
follows is a page that throws where somebody clicked rather than at a start, in
whichever window that line belongs to. Reading both files is what catches it, and
no browser has to be opened to do that.
"""

import re

import pytest

from conftest import INTERFACE, page_source

#: How the page reaches an element. getElementById is the plain way, and the rest
#: are this page's own helpers, which take an id and write into it.
BY_ID = re.compile(
    r'(?:getElementById|show|explain|fillWithChoices|fillWithBanks'
    r'|fillWithScale|drawPicture)\(\s*"([^"]+)"')

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
    return page_source()


@pytest.fixture(scope="module")
def markup():
    return (INTERFACE / "index.html").read_text(encoding="utf-8")


def inside(markup, window):
    """@returns str - One window's markup, from its tag to the next one's.

    Two windows show one subject at a time now, and their subjects are their
    own: a test that reads the whole document would hold each of them to the
    other's.
    """
    at = markup.index('<nx-window name="%s"' % window)
    after = markup.find("<nx-window ", at + 1)
    return markup[at:after if after > 0 else len(markup)]


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


def test_the_entry_about_this_machine_is_written_by_the_page(page, markup):
    """It carries the machine's own name, so the catalogue holds a sentence
    with a place in it rather than the words themselves. Given `data-t` as
    well, a change of language would write `Über {machine}` into the menu for
    the moment before the page filled it in."""
    entry = re.search(r'<nx-menu-item[^>]*name="about"[^>]*>', markup)

    assert entry, "the entry about this machine is not in the menu"
    assert "data-t=" not in entry.group(0)
    assert 'data-t-key="menu.about.key"' in entry.group(0)
    assert 't("menu.about"' in page


def test_an_entry_the_page_takes_out_stays_out(page):
    """The menu hides every entry belonging to another application each time
    the front window changes, so a page that used `hidden` for something else
    would have it put back a moment later. `away` is the page's word and the
    kit reads it."""
    kit = (INTERFACE / "nextstep.js").read_text(encoding="utf-8")

    assert 'hasAttribute("away")' in kit
    assert 'toggleAttribute("away"' in page


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
    does not offer is a group nobody can reach.

    Inside that window alone. Two windows use this arrangement now, and their
    subjects are their own.
    """
    offered = set(THE_SUBJECTS.findall(page))
    in_markup = set(A_GROUP_S_SUBJECT.findall(inside(markup, "editor")))

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


#: Every element of the Installer the page names. It reaches several of them
#: through a list rather than one at a time, which the pattern above does not
#: see, so they are caught by their names instead.
AN_INSTALLER_ELEMENT = re.compile(r'"(installer-[\w-]+)"')


def test_every_part_of_the_installer_the_page_names_is_in_the_markup(page, markup):
    """Its buttons are switched on and off through a list of names, so a typing
    mistake in one of those is a button that never changes and says nothing
    about it."""
    wanted = set(AN_INSTALLER_ELEMENT.findall(page))
    have = set(IN_MARKUP.findall(markup))

    assert len(wanted) > 5
    assert sorted(wanted - have) == []


#: What the Installer shows one of at a time, as the page names them.
THE_INSTALLER_TABS = re.compile(r'^  (\w+): "installer\.[\w.-]+",$', re.M)


def test_every_tab_the_installer_offers_has_a_group_to_show(page, markup):
    """The window shows one subject at a time, so a tab no group belongs to is
    a cell that empties the window, and a group belonging to no tab is a group
    nobody can reach."""
    offered = set(THE_INSTALLER_TABS.findall(page))
    in_markup = set(A_GROUP_S_SUBJECT.findall(inside(markup, "installer")))

    assert offered == {"emulator", "systems"}
    assert offered == in_markup


def test_the_installer_holds_no_list_of_systems(page):
    """What can be installed is decided by what can be fetched, and a second
    copy of that list in the page is how the two come to disagree. The window
    draws whatever the service offers, and there are no six of anything in it.

    By identifier, which is what the page would have to hold to name one. A
    system's name turns up in a comment explaining what comes with the
    emulator, and a comment is not a copy of anything.
    """
    from previously import systems

    for system in systems.CATALOGUE:
        assert system.identifier not in page, system.identifier


#: What the Installer names as a job, which is one table in the page written
#: out one entry per line.
A_JOB = re.compile(r"^const Install = \{(.*?)^\};", re.M | re.S)


def test_the_installer_asks_for_jobs_the_service_knows(page):
    """A name the service has no job for is refused, and the window would show
    that refusal rather than doing anything.

    One direction only. Two of the jobs are asked for by a route of their own
    rather than by name here, because copying a disk is started from the
    viewer, so the page naming fewer than the service knows is right.
    """
    from previously import setup

    table = A_JOB.search(page)
    assert table
    asked = set(re.findall(r'"([\w-]+)"', table.group(1)))

    assert asked
    assert asked <= set(setup.JOBS)


def test_every_scale_in_the_editor_is_a_slider(page, markup):
    """A group whose values have an order is a knob in a trough. Drawn as a row
    of cells it would say they have none, and more memory being to the right is
    the whole of what somebody reads off it."""
    for scale in ["editor-clocks", "editor-memory"]:
        assert '<nx-slider id="%s">' % scale in markup, scale
        assert '"%s"' % scale not in page.replace(
            'fillWithScale("%s"' % scale, ""), scale

    # The memory of a NeXTdimension board is the fourth, and its group is built
    # by the page because how many there are is what the slots decide.
    assert 'createElement("nx-slider")' in page


#: What cuts a version down to its release. One place decides it, so this is
#: what finding a second one looks like.
CUTS_A_VERSION = re.compile(r"\\d\+.*\\.\\d")


def test_only_one_thing_decides_what_a_version_reads_as():
    """A version of this tool is shown in three windows, and it carries the
    build it came from: `1.0.0+35.g553551d`. The interface shows the release
    alone. Written twice, the two would come to differ, and the way they would
    differ is one window saying something nobody else says about the same
    machine."""
    written = {
        path.name for path in sorted((INTERFACE / "app").glob("*.js"))
        if CUTS_A_VERSION.search(path.read_text(encoding="utf-8"))
    }

    assert written == {"words.js"}, written


def test_no_window_shows_a_version_of_ours_with_its_build_on_it():
    """Every place a version of this tool reaches the screen goes through that
    one function. The emulator's is not one of ours: `4.3-0wmlive1` is what
    dpkg calls that package, and cut down it would name a version that does not
    exist."""
    page = page_source()

    for reading in ['show("pi-version"', 'show("pi-newest"',
                    't("about.version"', 't("pi.update.done"',
                    't("pi.update.available"']:
        at = page.index(reading)
        # As far as the end of that call, which is where the value it shows is.
        assert "released(" in page[at:page.index("\n", at) + 120], reading


#: Which part of the window each of Preview's renderers fills.
A_RENDERER_S_ROOM = re.compile(r'^\s*room: "([^"]+)",$', re.M)


def test_every_renderer_fills_a_part_of_the_window_that_exists():
    """Preview hands the room to whichever renderer takes the document it was
    given, and it finds that room by a name the renderer carries rather than by
    a literal the rest of these tests would see. A name that is not in the
    markup answers nothing, and the window opens empty."""
    preview = (INTERFACE / "app" / "preview.js").read_text(encoding="utf-8")
    markup = (INTERFACE / "index.html").read_text(encoding="utf-8")
    rooms = set(A_RENDERER_S_ROOM.findall(preview))

    assert len(rooms) >= 2, rooms
    assert rooms <= set(IN_MARKUP.findall(markup)), rooms


def test_nothing_in_the_interface_writes_markup_from_a_string():
    """Release notes arrive from GitHub as text somebody wrote, and they reach
    a page. `markdown.js` turns them into elements one at a time, which is what
    makes escaping structural rather than a thing to remember, and this is what
    says nobody took the shorter road anywhere else either."""
    written = {
        path.name for path in sorted((INTERFACE / "app").glob("*.js"))
        if "innerHTML" in path.read_text(encoding="utf-8")
    }

    assert written == set(), written
