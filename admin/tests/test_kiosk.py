"""Starting and stopping the emulator.

None of this needs a compositor or a running emulator. What is faked is the
world outside the module: whether a process exists and whether a key reached
the screen. What is tested is the order of operations, which is the whole of
the design and the only part that can be wrong in a way that costs a file
system check.
"""

import pytest

from previously import kiosk

#: The genuine press, kept before any fixture replaces it. Two tests below are
#: about what press_power itself does, so a fake one would test the fake.
REAL_PRESS_POWER = kiosk.press_power


@pytest.fixture
def world(tmp_path, monkeypatch):
    """A fake machine this module can act on.

    @returns an object recording what was done and letting a test say what the
      emulator does in response.
    """
    class World:
        def __init__(self):
            self.emulator_running = True
            self.power_pressed = 0
            self.power_works = True
            #: How many polls the guest takes to go. None means it never does.
            self.shutdown_after_polls = 1
            self.polls = 0

        def emulator_is_running(self):
            return self.emulator_running

        def press_power(self):
            self.power_pressed += 1
            return self.power_works

        def sleep(self, _seconds):
            self.polls += 1
            if (self.shutdown_after_polls is not None
                    and self.polls >= self.shutdown_after_polls):
                self.emulator_running = False

    answer = World()
    monkeypatch.setattr(kiosk, "emulator_is_running", answer.emulator_is_running)
    monkeypatch.setattr(kiosk, "press_power", answer.press_power)
    return answer


# -- the hold file -------------------------------------------------------


def test_nothing_is_held_to_begin_with(tmp_path):
    assert kiosk.is_held(tmp_path) is False


def test_the_hold_file_sits_in_the_state_directory(tmp_path):
    """The one place the unit's hardening lets this service write."""
    assert kiosk.hold_path(tmp_path).parent == tmp_path


# -- stopping ------------------------------------------------------------


def test_stopping_holds_before_it_presses(tmp_path, world):
    """The order is the whole design. A key pressed before the hold is in place
    leaves a gap in which the session ends and the emulator comes straight
    back, which is the race this exists to avoid."""
    order = []

    def record_press():
        order.append("held" if kiosk.is_held(tmp_path) else "not held")
        world.emulator_running = False
        return True

    import unittest.mock
    with unittest.mock.patch.object(kiosk, "press_power", record_press):
        kiosk.stop(tmp_path, sleep=world.sleep)

    assert order == ["held"]


def test_stopping_presses_the_power_button_once(tmp_path, world):
    finished, reason = kiosk.stop(tmp_path, sleep=world.sleep)

    assert finished is True
    assert world.power_pressed == 1
    assert "shut itself down" in reason


def test_stopping_leaves_the_emulator_held(tmp_path, world):
    kiosk.stop(tmp_path, sleep=world.sleep)
    assert kiosk.is_held(tmp_path) is True


def test_stopping_something_already_stopped_still_holds_it(tmp_path, world):
    """Otherwise the console's waiting profile would start it again a second
    later, and the tool would have done the opposite of what was asked."""
    world.emulator_running = False

    finished, reason = kiosk.stop(tmp_path, sleep=world.sleep)

    assert finished is True
    assert kiosk.is_held(tmp_path) is True
    assert world.power_pressed == 0
    assert "was not running" in reason


def test_a_key_that_does_not_arrive_changes_nothing(tmp_path, world):
    """Leaving the hold in place after a failed press would stop the emulator
    at its next restart, hours later, for a reason nobody would connect to
    this."""
    world.power_works = False

    finished, reason = kiosk.stop(tmp_path, sleep=world.sleep)

    assert finished is False
    assert kiosk.is_held(tmp_path) is False
    assert "nothing was changed" in reason


def test_a_guest_that_does_not_go_is_reported_rather_than_killed(tmp_path, world):
    """The one case where waiting longer is right, so the tool says so and
    stops rather than reaching for anything harder."""
    world.shutdown_after_polls = None

    finished, reason = kiosk.stop(tmp_path, timeout=3, sleep=world.sleep)

    assert finished is False
    assert "has not finished shutting down" in reason
    # Still held, because the guest is still going and must not be restarted
    # underneath itself.
    assert kiosk.is_held(tmp_path) is True


def test_waiting_gives_the_guest_the_whole_timeout(tmp_path, world):
    """NeXTSTEP flushes and unmounts at its own pace."""
    world.shutdown_after_polls = 5

    finished, _ = kiosk.stop(tmp_path, timeout=60, sleep=world.sleep)

    assert finished is True
    assert world.polls == 5


# -- starting ------------------------------------------------------------


def test_starting_removes_the_hold(tmp_path, world):
    kiosk.stop(tmp_path, sleep=world.sleep)

    finished, reason = kiosk.start(tmp_path)

    assert finished is True
    assert kiosk.is_held(tmp_path) is False
    assert "on its way back" in reason


def test_starting_something_already_running_says_so(tmp_path, world):
    finished, reason = kiosk.start(tmp_path)

    assert finished is True
    assert "already running" in reason


def test_starting_is_not_an_error_when_nothing_holds_and_nothing_runs(tmp_path, world):
    """The window between the hold coming off and the console noticing."""
    world.emulator_running = False

    finished, reason = kiosk.start(tmp_path)

    assert finished is True
    assert "should come back on its own" in reason


# -- restarting ----------------------------------------------------------


def test_restarting_shuts_down_and_lets_it_come_back(tmp_path, world):
    finished, reason = kiosk.restart(tmp_path, sleep=world.sleep)

    assert finished is True
    assert world.power_pressed == 1
    assert kiosk.is_held(tmp_path) is False
    assert "on its way back" in reason


def test_a_restart_that_cannot_shut_down_does_not_start_anything(tmp_path, world):
    """Releasing the hold here would let the console start a second emulator
    beside a guest that is still writing."""
    world.shutdown_after_polls = None

    finished, reason = kiosk.restart(tmp_path, timeout=3, sleep=world.sleep)

    assert finished is False
    assert kiosk.is_held(tmp_path) is True
    assert "has not finished shutting down" in reason


# -- the keys themselves -------------------------------------------------


def test_the_power_button_is_the_power_key(tmp_path, monkeypatch):
    """Answering the panel it raises is the waiting's business, because when
    that panel appears is the guest's business and not ours."""
    sent = []
    monkeypatch.setattr(kiosk, "_press", lambda key: sent.append(key) or True)

    assert kiosk.press_power() is True
    assert sent == [kiosk.POWER_KEY]


def test_the_confirmation_is_pressed_again_until_the_guest_goes(tmp_path, world, monkeypatch):
    """NeXTSTEP raises its panel at its own pace, and a machine that has been
    up for hours with windows open is slower about it than one that has just
    started. One press at a fixed moment lands on the desktop when the panel is
    not up yet, and the panel then stands unanswered until the time runs out.
    That happened on the machine on 14 September 2026."""
    sent = []
    monkeypatch.setattr(kiosk, "_press", lambda key: sent.append(key) or True)
    monkeypatch.setattr(kiosk, "press_power", REAL_PRESS_POWER)
    world.shutdown_after_polls = 9

    finished, _ = kiosk.stop(tmp_path, sleep=world.sleep)

    assert finished is True
    assert sent[0] == kiosk.POWER_KEY
    # Pressed more than once, because the guest took nine looks to go.
    assert sent.count(kiosk.CONFIRM_KEY) > 1


def test_a_power_key_that_does_not_arrive_stops_there(tmp_path, world, monkeypatch):
    """A stray return key would reach whatever the guest is showing."""
    sent = []

    def refuse(key):
        sent.append(key)
        return False

    monkeypatch.setattr(kiosk, "_press", refuse)
    monkeypatch.setattr(kiosk, "press_power", REAL_PRESS_POWER)

    finished, reason = kiosk.stop(tmp_path, sleep=world.sleep)

    assert finished is False
    assert "nothing was changed" in reason
    assert sent == [kiosk.POWER_KEY]


def test_no_x_server_means_no_key(tmp_path, monkeypatch):
    """The emulator is not running, so there is nothing to press against."""
    monkeypatch.setattr(kiosk, "X11_SOCKETS", str(tmp_path / "absent"))
    assert kiosk._press(kiosk.POWER_KEY) is False


def test_the_display_comes_from_the_socket(tmp_path, monkeypatch):
    """Xwayland picks the number, so it is read rather than assumed."""
    monkeypatch.setattr(kiosk, "X11_SOCKETS", str(tmp_path))
    (tmp_path / "X7").touch()

    assert kiosk._display() == ":7"


# -- the board itself ----------------------------------------------------


@pytest.fixture
def board(tmp_path):
    """Where a request to the board would be left."""
    return tmp_path


def test_the_guest_goes_down_before_the_board_does(tmp_path, world, board):
    """A board that reboots underneath a running emulator does the same damage
    as killing the emulator, and to a machine that then has to come back."""
    order = []

    def watch_power(_sleep=None):
        order.append("guest")
        world.emulator_running = False
        return True

    def watch_request(runtime_directory, action):
        order.append("board")
        return True

    import unittest.mock
    with unittest.mock.patch.object(kiosk, "press_power", watch_power), \
            unittest.mock.patch.object(kiosk, "_request", watch_request):
        finished, _ = kiosk.board("reboot", tmp_path, sleep=world.sleep)

    assert finished is True
    assert order == ["guest", "board"]


def test_rebooting_leaves_the_request_the_path_unit_watches_for(tmp_path, world):
    """The name of the file is the whole of the request: previously-reboot.path
    watches for this one and nothing is passed to it."""
    kiosk.board("reboot", tmp_path, sleep=world.sleep)
    assert (tmp_path / "reboot").exists()
    assert not (tmp_path / "poweroff").exists()


def test_switching_the_board_off_leaves_the_other_one(tmp_path, world):
    kiosk.board("poweroff", tmp_path, sleep=world.sleep)
    assert (tmp_path / "poweroff").exists()
    assert not (tmp_path / "reboot").exists()


def test_nothing_else_can_be_asked_of_the_board(tmp_path, world):
    """A name with no pair of units behind it is a request nothing answers, so
    it is refused here rather than left lying in the runtime directory. And the
    guest is not shut down for it."""
    finished, reason = kiosk.board("halt-and-catch-fire", tmp_path, sleep=world.sleep)

    assert finished is False
    assert "keine Aktion" in reason
    assert list(tmp_path.iterdir()) == []
    assert world.power_pressed == 0


def test_a_guest_that_will_not_go_leaves_the_board_alone(tmp_path, world):
    world.shutdown_after_polls = None

    finished, reason = kiosk.board("reboot", tmp_path, timeout=3, sleep=world.sleep)

    assert finished is False
    assert "has not finished shutting down" in reason
    assert not (tmp_path / "reboot").exists()


def test_the_hold_is_left_in_place(tmp_path, world):
    """Nothing releases it and nothing needs to: it is on a tmpfs, so the board
    comes back to an empty runtime directory and the console starts the
    emulator by itself."""
    kiosk.board("reboot", tmp_path, sleep=world.sleep)
    assert kiosk.is_held(tmp_path) is True


def test_a_request_that_cannot_be_written_is_reported(tmp_path, world, monkeypatch):
    """The guest is already down by then, so saying so is the whole of what can
    be done about it."""
    monkeypatch.setattr(kiosk, "_request", lambda _directory, _action: False)

    finished, reason = kiosk.board("poweroff", tmp_path, sleep=world.sleep)

    assert finished is False
    assert "nicht darum bitten" in reason
    assert "SSH" in reason


def test_a_runtime_directory_that_is_not_there_is_not_an_exception(tmp_path):
    """Every other reading in this tool answers rather than raises, and a
    request that cannot be left is the same kind of thing."""
    assert kiosk._request(tmp_path / "gone", "reboot") is False
