"""The six catalogues, held against each other and against the code.

Six files answering the same question drift, and the way they drift is
invisible: a missing entry falls back to English, so the interface goes on
working and one line of it is in the wrong language. Nothing on the screen says
so. These tests are what says so.

The catalogues are read as text rather than run, because this suite has no
JavaScript in it and one entry per line is all that needs to be understood.
"""

import re

import pytest

from previously.server import WEB_ROOT

#: Where the catalogues live, English first because it is the one the others
#: are measured against.
LANGUAGES = ["en", "de", "fr", "it", "es", "sv"]

#: One entry of a catalogue: a quoted key, a colon, a quoted sentence.
ENTRY = re.compile(r'^\s*"([^"]+)":\s*"(.*)",\s*$')

#: What fills a place in a sentence, such as `{machine}`.
PLACE = re.compile(r"\{(\w+)\}")

#: A string asked for by its own name, so `t("info.disk")`. What is built from
#: a value at the moment of asking is caught by the tests further down, which
#: come at it from the service's side.
LOOKUP = re.compile(r'\bt\(\s*"([^"]+)"')

#: How the service names what happened, one per answer it can give.
TOLD = re.compile(r'told\(\s*"([^"]+)"')


def catalogue(language):
    """@returns dict of every entry in one language."""
    text = (WEB_ROOT / "lang" / f"{language}.js").read_text(encoding="utf-8")
    found = {}
    for line in text.splitlines():
        match = ENTRY.match(line)
        if match:
            found[match.group(1)] = match.group(2)
    return found


@pytest.fixture(scope="module")
def english():
    return catalogue("en")


def test_the_english_catalogue_is_not_empty(english):
    """Every test below measures against English, so an English catalogue that
    failed to parse would make all of them pass on nothing."""
    assert len(english) > 100


@pytest.mark.parametrize("language", [code for code in LANGUAGES if code != "en"])
def test_every_language_says_everything_english_says(language, english):
    other = catalogue(language)
    missing = sorted(set(english) - set(other))
    spare = sorted(set(other) - set(english))

    assert missing == [], f"{language} is missing these"
    assert spare == [], f"{language} has these and English does not"


@pytest.mark.parametrize("language", [code for code in LANGUAGES if code != "en"])
def test_every_sentence_has_the_same_places(language, english):
    """A place left out of one language drops the number or the name from that
    language alone, which is the kind of fault nobody sees until they read the
    interface in it."""
    other = catalogue(language)
    differ = {
        key: (sorted(PLACE.findall(english[key])), sorted(PLACE.findall(line)))
        for key, line in other.items()
        if key in english
        and sorted(PLACE.findall(english[key])) != sorted(PLACE.findall(line))
    }

    assert differ == {}


def test_the_markup_asks_for_strings_that_exist(english):
    """The interface's own labels, which carry a key and no words at all, so a
    key that is not in the catalogue shows on the screen as itself."""
    markup = (WEB_ROOT / "index.html").read_text(encoding="utf-8")
    wanted = set(re.findall(r'data-t(?:-title)?="([^"]+)"', markup))

    assert sorted(wanted - set(english)) == []


def test_the_page_asks_for_strings_that_exist(english):
    """Every string the page looks up by name. Plurals are asked for without
    their ending, which the browser chooses, so both endings count as the key
    being there."""
    page = (WEB_ROOT / "app.js").read_text(encoding="utf-8")
    plurals = {key.rsplit(".", 1)[0] for key in english if key.endswith((".one", ".other"))}

    missing = [
        key for key in sorted(set(LOOKUP.findall(page)))
        if key not in english and key not in plurals
    ]

    assert missing == []


def test_every_answer_the_service_can_give_has_a_sentence(english):
    """The service sends a name for what happened. A name nothing can say is a
    name that reaches the screen as it is."""
    service = ""
    for name in ["kiosk.py", "change.py", "saved.py", "server.py"]:
        service += (WEB_ROOT.parent / "previously" / name).read_text(encoding="utf-8")

    for reason in sorted(set(TOLD.findall(service))):
        key = f"told.{reason}"
        assert key in english or any(other.startswith(key + ".") for other in english), key


def test_every_application_can_be_named_in_words(english):
    """An application is shown by its bundle and spoken of by its name, and the
    second of those is a key. One nothing can say reaches the screen as it
    is."""
    from previously import files

    wanted = {label for _, _, _, label in files.APPLICATIONS}

    assert sorted(wanted - set(english)) == []


def test_nothing_in_the_viewer_is_shown_by_a_key(english):
    """A viewer shows names, so a folder, a machine and the root are drawn as
    they are called. Only an application carries a key, and that one is for
    what it is called in words rather than for what stands under its picture.
    """
    from previously import files

    tree = files.tree()
    apps, documents, machines = tree["entries"]
    pictures = documents["entries"][0]
    system = machines["entries"][0]

    assert tree["name"] == "Previously"
    for folder in [tree, apps, documents, pictures, machines, system]:
        assert "label" not in folder or folder["label"] is None, folder["name"]
    assert system["entries"]
    assert all("label" not in machine for machine in system["entries"])
    assert all(entry["label"] for entry in apps["entries"])


def test_every_word_the_board_can_report_has_a_sentence(english):
    """The four names for what a Raspberry Pi does to itself when the power or
    the temperature is not what it wants."""
    from previously import pi

    for name in set(pi.THROTTLING_NOW.values()) | set(pi.THROTTLING_SINCE_BOOT.values()):
        assert f"throttling.{name}" in english


#: One entry of the main menu, with whatever attributes it carries.
MENU_ITEM = re.compile(r"<nx-menu-item\b([^>]*)>")

#: What an entry says its letter and its words are called.
KEY_OF = re.compile(r'data-t-key="([^"]+)"')
WORDS_OF = re.compile(r'data-t="([^"]+)"')


#: Which application an entry belongs to, or nothing for the workspace's own.
OWNER_OF = re.compile(r'\bfor="([^"]+)"')


def menus():
    """@returns dict of owner to list of (letter key, words key or None).

    The main menu only, and one list per application whose entries live in it.
    A context menu's entries act on what was right clicked, and no key press
    reaches them.

    The main menu is one menu whose contents are replaced, so the letters have
    to be distinct within each application's set rather than across all of
    them: only one set is ever showing.
    """
    markup = (WEB_ROOT / "index.html").read_text(encoding="utf-8")
    menu = re.search(r'<nx-menu name="menu".*?</nx-menu>', markup, re.S)
    assert menu, "the main menu is not in the markup"

    found = {}
    for attributes in MENU_ITEM.findall(menu.group(0)):
        letter = KEY_OF.search(attributes)
        words = WORDS_OF.search(attributes)
        owner = OWNER_OF.search(attributes)
        assert letter, attributes
        found.setdefault(owner.group(1) if owner else "", []).append(
            (letter.group(1), words.group(1) if words else None))
    return found


def test_the_main_menu_has_entries_to_check():
    assert len(menus()[""]) >= 5
    assert len(menus()) > 1, "no application carries a menu of its own"


@pytest.mark.parametrize("language", LANGUAGES)
def test_no_two_menu_entries_share_a_letter(language):
    """The page acts on the first entry whose letter matches, so a letter used
    twice makes the second entry unreachable and says nothing about it. Within
    one application, because only one application's entries are ever up."""
    words = catalogue(language)
    for owner, entries in menus().items():
        letters = [words[key] for key, _ in entries if key in words]
        assert len(letters) == len(set(letters)), (owner, letters)


@pytest.mark.parametrize("language", LANGUAGES)
def test_every_menu_letter_is_in_the_word_beside_it(language):
    """A shortcut whose letter is not in its word is one nobody will guess,
    which is the thing this is for."""
    words = catalogue(language)
    for entries in menus().values():
        for key, shown in entries:
            if shown is None:
                continue
            assert key in words, key
            assert shown in words, shown
            assert words[key].lower() in words[shown].lower(), (
                key, words[key], words[shown])
