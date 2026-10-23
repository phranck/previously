"""The wire that reaches the emulator.

What is faked is the command that asks the X server. What is tested is how the
emulator's window is found, because every key this service sends goes to it.
"""

from previously import screen


def asking(monkeypatch, answer):
    """Lets a test say what xdotool replies to each search.

    @param answer - What it replies, given the pattern searched for.
    @returns list of the commands that were run.
    """
    asked = []

    def fake_ask(command):
        asked.append(command)
        return answer(command[-1])

    monkeypatch.setattr(screen, "_ask", fake_ask)
    monkeypatch.setattr(screen.shutil, "which", lambda name: "/usr/bin/" + name)
    return asked


def test_the_window_is_asked_for_by_name_first(monkeypatch):
    """Previous names its window after itself, and the id it gets from the X
    server changes at every start."""
    asked = asking(monkeypatch, lambda pattern: "12345")

    assert screen.window() == "12345"
    assert asked[0] == ["xdotool", "search", "--name", screen.WINDOW]


def test_a_window_that_does_not_answer_to_its_name_is_still_found(monkeypatch):
    """Under cage's Xwayland the name is not where xdotool looks for it, and
    the only window on that display is the emulator's. Measured on the machine:
    searching for the name found nothing and searching for anything found
    4194359."""
    asked = asking(monkeypatch,
                   lambda pattern: "4194359" if pattern == screen.ANY_WINDOW else "")

    assert screen.window() == "4194359"
    assert asked[1] == ["xdotool", "search", "--name", screen.ANY_WINDOW]


def test_no_window_means_none(monkeypatch):
    asking(monkeypatch, lambda pattern: "")

    assert screen.window() is None


def test_without_xdotool_there_is_no_window(monkeypatch):
    monkeypatch.setattr(screen.shutil, "which", lambda name: None)

    assert screen.window() is None


# -- where the screen is -------------------------------------------------


def test_the_display_comes_from_the_socket(tmp_path, monkeypatch):
    """Xwayland picks the number, so it is read rather than assumed."""
    monkeypatch.setattr(screen, "X11_SOCKETS", str(tmp_path))
    (tmp_path / "X7").touch()

    assert screen.display() == ":7"


def test_no_socket_means_no_display(tmp_path, monkeypatch):
    monkeypatch.setattr(screen, "X11_SOCKETS", str(tmp_path / "absent"))

    assert screen.display() is None
