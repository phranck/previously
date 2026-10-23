"""The emulator's process, and the keyboard that reaches it.

/dev/uinput is not here, so what is faked is the kernel's side: the device
that opens, the requests it takes and the events written to it. What is tested
is what this module tells the kernel, in which order and in which bytes, and
when it tells it nothing at all. That the keys reach Previous under cage was
checked on a Pi 4 and a Pi 5.
"""

import pytest

from previously import emulator


@pytest.fixture
def kernel(monkeypatch):
    """A /dev/uinput that records what it is told.

    @returns object with `opened`, `requests` and `events`.
    """
    class Kernel:
        def __init__(self):
            self.opened = 0
            self.refuses = False
            self.requests = []
            self.events = []
            self.fails_to_write = False

        def open(self, path, flags):
            if self.refuses:
                raise PermissionError(path)
            self.opened += 1
            return 7

        def ioctl(self, device, request, argument=0):
            self.requests.append((request, argument))
            return 0

        def write(self, device, data):
            if self.fails_to_write:
                raise OSError("gone")
            self.events.append(emulator.EVENT.unpack(data)[2:])
            return len(data)

    answer = Kernel()
    monkeypatch.setattr(emulator, "_DEVICE", None)
    monkeypatch.setattr(emulator.os, "open", answer.open)
    monkeypatch.setattr(emulator.os, "write", answer.write)
    monkeypatch.setattr(emulator.os, "close", lambda device: None)
    monkeypatch.setattr(emulator.fcntl, "ioctl", answer.ioctl)
    monkeypatch.setattr(emulator.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(emulator, "pid", lambda: 1234)
    return answer


def keys_in(events):
    """@returns list of (code, down) for the key events, without the reports."""
    return [(code, value) for kind, code, value in events if kind == emulator.EV_KEY]


def test_a_key_goes_down_and_comes_back_up(kernel):
    assert emulator.press("F10") is True

    assert keys_in(kernel.events) == [(68, 1), (68, 0)]


def test_every_key_event_is_followed_by_a_report(kernel):
    """The compositor acts on a key only once the report after it arrives."""
    emulator.press("Return")

    assert kernel.events == [(emulator.EV_KEY, 28, 1),
                             (emulator.EV_SYN, emulator.SYN_REPORT, 0),
                             (emulator.EV_KEY, 28, 0),
                             (emulator.EV_SYN, emulator.SYN_REPORT, 0)]


def test_modifiers_are_held_first_and_let_go_last(kernel):
    emulator.press("ctrl+alt+g")

    assert keys_in(kernel.events) == [(29, 1), (56, 1), (34, 1),
                                      (34, 0), (56, 0), (29, 0)]


def test_the_keyboard_is_made_able_to_send_these_keys_and_no_others(kernel):
    emulator.press("F10")

    bits = [argument for request, argument in kernel.requests
            if request == emulator.UI_SET_KEYBIT]
    assert sorted(bits) == sorted(emulator.KEYS.values())
    assert (emulator.UI_SET_EVBIT, emulator.EV_KEY) in kernel.requests


def test_the_keyboard_is_described_before_it_is_made(kernel):
    emulator.press("F10")

    order = [request for request, _ in kernel.requests]
    assert order.index(emulator.UI_DEV_SETUP) < order.index(emulator.UI_DEV_CREATE)
    assert order[-1] == emulator.UI_DEV_CREATE
    described = dict(kernel.requests)[emulator.UI_DEV_SETUP]
    bus, _, _, _, name, _ = emulator.SETUP.unpack(described)
    assert bus == emulator.BUS_VIRTUAL
    assert name.rstrip(b"\0") == emulator.NAME


def test_the_keyboard_is_made_once_and_kept(kernel):
    """The compositor needs a moment for a new keyboard, so a fresh one per
    key would lose the key."""
    emulator.press("F10")
    emulator.press("Return")

    assert kernel.opened == 1


def test_a_name_the_keyboard_does_not_have_is_not_pressed(kernel):
    assert emulator.press("ctrl+alt+x") is False
    assert kernel.opened == 0


def test_no_key_reaches_a_board_without_an_emulator(kernel, monkeypatch):
    """With no compositor holding the keyboard, its keys reach the text
    console, where the login shell that starts the emulator waits."""
    monkeypatch.setattr(emulator, "pid", lambda: None)

    assert emulator.press("Return") is False
    assert kernel.opened == 0
    assert kernel.events == []


def test_a_device_that_cannot_be_opened_sends_nothing(kernel):
    """What a board without the package's udev rule comes to."""
    kernel.refuses = True

    assert emulator.press("F10") is False


def test_a_keyboard_that_fails_is_made_afresh(kernel):
    kernel.fails_to_write = True
    assert emulator.press("F10") is False

    kernel.fails_to_write = False
    assert emulator.press("F10") is True
    assert kernel.opened == 2


def test_the_requests_are_the_ones_linux_uinput_h_builds():
    """_IO('U', 1), _IOW('U', 3, struct uinput_setup) and _IOW('U', 100 and
    101, int), worked out from the header's own macros."""
    assert emulator.UI_DEV_CREATE == 0x5501
    assert emulator.UI_DEV_SETUP == 0x405C5503
    assert emulator.UI_SET_EVBIT == 0x40045564
    assert emulator.UI_SET_KEYBIT == 0x40045565


def test_the_structures_are_the_sizes_the_kernel_reads():
    """struct uinput_setup is 92 bytes, and struct input_event 24 on a 64-bit
    board, where a timeval is two longs."""
    assert emulator.SETUP.size == 92
    assert emulator.EVENT.size == 24


def test_the_emulator_is_found_by_its_process_name(monkeypatch):
    class Answer:
        stdout = "4242\n"

    asked = []
    monkeypatch.setattr(emulator.subprocess, "run",
                        lambda command, **how: asked.append(command) or Answer())

    assert emulator.pid() == 4242
    assert asked == [["pgrep", "-x", emulator.PROCESS]]


def test_no_emulator_is_none(monkeypatch):
    class Answer:
        stdout = ""

    monkeypatch.setattr(emulator.subprocess, "run", lambda command, **how: Answer())

    assert emulator.pid() is None
