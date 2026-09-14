"""Reading the emulated screen.

What is faked is the pair of commands that reach the X server. What is tested
is the judgement made on what they answer, because that judgement decides
whether a machine gets rolled back.
"""

import pytest

from previously import screen


@pytest.fixture
def answers(monkeypatch):
    """Lets a test say what the two commands reply.

    @returns dict keyed by the command's name.
    """
    replies = {"xdotool": "4194359", "import": "15045.3"}

    def fake_ask(command):
        return replies.get(command[0], "")

    monkeypatch.setattr(screen, "_ask", fake_ask)
    monkeypatch.setattr(screen.shutil, "which", lambda name: "/usr/bin/" + name)
    return replies


def test_a_screen_with_something_on_it_is_alive(answers):
    assert screen.looks_alive() is True


def test_a_screen_of_one_flat_colour_is_not(answers):
    """A machine that never booted. The emulator is running and its window is
    there, and nothing has been drawn in it."""
    answers["import"] = "0"

    assert screen.looks_alive() is False


def test_the_boot_panel_alone_is_enough(answers):
    """The ROM puts its panel up before NeXTSTEP loads, so a machine caught
    mid-boot must not read as blank."""
    answers["import"] = "5311.26"

    assert screen.looks_alive() is True


def test_no_window_means_no_reading(answers):
    """Not False: a machine that is not running has no screen to be blank."""
    answers["xdotool"] = ""

    assert screen.looks_alive() is None


def test_an_answer_that_is_not_a_number_is_no_reading(answers):
    answers["import"] = "import: unable to read X window image"

    assert screen.looks_alive() is None


def test_without_the_tools_nothing_is_claimed(answers, monkeypatch):
    """A missing package must not make every machine look broken."""
    monkeypatch.setattr(screen.shutil, "which", lambda name: None)

    assert screen.looks_alive() is None


def test_the_window_is_asked_for_by_name_first(answers, monkeypatch):
    """Previous names its window after itself, and the id it gets from the X
    server changes at every start."""
    asked = []
    monkeypatch.setattr(screen, "_ask", lambda command: asked.append(command) or "12345")

    screen.looks_alive()

    assert asked[0] == ["xdotool", "search", "--name", screen.WINDOW]
    assert asked[1][:4] == ["import", "-window", "12345", "-trim"]


def test_a_window_that_does_not_answer_to_its_name_is_still_found(monkeypatch):
    """Under cage's Xwayland the name is not where xdotool looks for it, and
    the only window on that display is the emulator's. Measured on the machine:
    searching for the name found nothing and searching for anything found
    4194359."""
    asked = []

    def fake_ask(command):
        asked.append(command)
        if command[0] == "import":
            return "15045.3"
        return "4194359" if command[-1] == screen.ANY_WINDOW else ""

    monkeypatch.setattr(screen, "_ask", fake_ask)
    monkeypatch.setattr(screen.shutil, "which", lambda name: "/usr/bin/" + name)

    assert screen.looks_alive() is True
    assert asked[1] == ["xdotool", "search", "--name", screen.ANY_WINDOW]
    assert asked[2][:4] == ["import", "-window", "4194359", "-trim"]


# -- where the screen is -------------------------------------------------


def test_the_display_comes_from_the_socket(tmp_path, monkeypatch):
    """Xwayland picks the number, so it is read rather than assumed."""
    monkeypatch.setattr(screen, "X11_SOCKETS", str(tmp_path))
    (tmp_path / "X7").touch()

    assert screen.display() == ":7"


def test_no_socket_means_no_display(tmp_path, monkeypatch):
    monkeypatch.setattr(screen, "X11_SOCKETS", str(tmp_path / "absent"))

    assert screen.display() is None
