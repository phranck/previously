"""What the Pi decides is worth telling whoever has the admin open."""

import pytest

from previously import notices, pi, setup

#: A board with nothing to say about itself.
QUIET = {
    "temperature_c": 52.1,
    "throttling": {"raw": 0, "now": [], "since_boot": []},
    "disk": {"free_mb": 20000, "total_mb": 30000, "used_percent": 33},
    "crashes": None,
}

#: This tool and Previous, both up to date.
CURRENT = {"installed": "1.12.4", "published": "1.12.4"}
EMULATOR = {"version": "4.5-0wmlive1", "newest": "4.5-0wmlive1"}


def by_version(version, other):
    """dpkg's ordering for these plain versions, so a test needs no dpkg."""
    if not version or not other:
        return False
    return tuple(int(part) for part in version.split("-")[0].split(".")) \
        < tuple(int(part) for part in other.split("-")[0].split("."))


@pytest.fixture(autouse=True)
def without_dpkg(monkeypatch):
    monkeypatch.setattr(setup, "newer_than", by_version)


def said(tool=CURRENT, emulator=EMULATOR, board=QUIET, running=False):
    """@returns dict from each notification's name to what it carries."""
    return {notice["name"]: notice
            for notice in notices.worth_saying(tool, emulator, board, running)}


def test_a_current_tool_on_a_quiet_board_says_nothing():
    assert said() == {}


def test_a_newer_release_is_offered_by_its_version():
    update = said(tool={"installed": "1.12.4", "published": "1.13.0"})["update"]

    assert update["level"] == notices.Level.INFO
    assert update["reading"] == "1.13.0"
    assert update["values"] == {"version": "1.13.0", "installed": "1.12.4"}


def test_a_release_not_yet_known_offers_nothing():
    assert said(tool={"installed": "1.12.4", "published": None}) == {}


def test_a_newer_previous_is_offered_by_its_version():
    emulator = said(emulator={"version": "4.4-0wmlive1",
                              "newest": "4.5-0wmlive1"})["emulator"]

    assert emulator["level"] == notices.Level.INFO
    assert emulator["reading"] == "4.5-0wmlive1"


def test_a_previous_that_is_not_installed_is_not_offered_an_update():
    assert said(emulator={"version": None, "newest": "4.5-0wmlive1"}) == {}


def test_no_update_is_offered_while_the_helper_is_busy():
    """The window that started the job is already saying how it goes."""
    assert said(tool={"installed": "1.12.4", "published": "1.13.0"},
                emulator={"version": "4.4-0wmlive1", "newest": "4.5-0wmlive1"},
                running=True) == {}


def test_under_voltage_now_is_said():
    board = dict(QUIET, throttling={"raw": 1, "now": ["under-voltage"],
                                    "since_boot": ["under-voltage"]})

    assert said(board=board)["power"]["level"] == notices.Level.ALERT


def test_under_voltage_that_was_and_is_not_now_is_not_said():
    """The moment a drive was plugged in is worth knowing in the window and
    not worth interrupting anybody for."""
    board = dict(QUIET, throttling={"raw": 0x10000, "now": [],
                                    "since_boot": ["under-voltage"]})

    assert said(board=board) == {}


def test_the_temperature_is_said_from_the_limit_the_board_window_marks():
    just_under = dict(QUIET, temperature_c=pi.TEMPERATURE_LIMIT_C - 0.1)
    at_it = dict(QUIET, temperature_c=float(pi.TEMPERATURE_LIMIT_C))

    assert said(board=just_under) == {}
    assert said(board=at_it)["temperature"]["values"] == {
        "temperature": pi.TEMPERATURE_LIMIT_C, "limit": pi.TEMPERATURE_LIMIT_C}


def test_a_card_that_is_nearly_full_is_said():
    below = dict(QUIET, disk={"free_mb": 4000, "total_mb": 30000,
                              "used_percent": notices.DISK_FULL_PERCENT - 1})
    full = dict(QUIET, disk={"free_mb": 3000, "total_mb": 30000,
                             "used_percent": notices.DISK_FULL_PERCENT})

    assert said(board=below) == {}
    assert said(board=full)["disk"]["values"] == {
        "percent": notices.DISK_FULL_PERCENT, "free_mb": 3000}


def test_a_crash_is_an_error_that_comes_back_with_the_next_one():
    """Closing it closes the crashes so far. The next crash is news."""
    one = said(board=dict(QUIET, crashes={"count": 1, "last": 1790654464}))
    two = said(board=dict(QUIET, crashes={"count": 2, "last": 1790657571}))

    assert one["crash"]["level"] == notices.Level.ERROR
    assert one["crash"]["reading"] != two["crash"]["reading"]


def test_readings_the_board_could_not_take_say_nothing():
    blank = {"temperature_c": None, "throttling": None, "disk": None,
             "crashes": None}

    assert said(board=blank) == {}


def test_what_is_known_is_asked_again_once_it_is_an_hour_old(monkeypatch):
    asked = []

    def keeper(name, asked_at):
        def answer(check=False):
            if check:
                asked.append(name)
            return {"version": "1", "asked_at": asked_at}
        return answer

    monkeypatch.setattr(notices.release, "published", keeper("release", 0.0))
    monkeypatch.setattr(notices.archive, "offered",
                        keeper("archive", notices.FRESH_SECONDS))

    notices.look_again(now=notices.FRESH_SECONDS)

    assert asked == ["release"]


def test_what_was_never_learned_is_asked_for(monkeypatch):
    asked = []

    def unknown(check=False):
        if check:
            asked.append(True)

    monkeypatch.setattr(notices.release, "published", unknown)
    monkeypatch.setattr(notices.archive, "offered", unknown)

    notices.look_again(now=1.0)

    assert asked == [True, True]
