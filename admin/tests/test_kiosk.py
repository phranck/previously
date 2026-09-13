"""Starting and stopping the emulator.

None of this needs a compositor or a running emulator. What is faked is the
world outside the module: whether a process exists and whether a key reached
the screen. What is tested is the order of operations, which is the whole of
the design and the only part that can be wrong in a way that costs a file
system check.
"""

import pytest

from previously import kiosk


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
