"""Changing the machine, and what happens when it will not come back.

The fixture is a real previous.cfg, cut from the one on the machine, so what is
tested is the file that exists rather than one shaped to be convenient.
"""

import textwrap

import pytest

from previously import change, config, kiosk

REAL_SHAPE = textwrap.dedent("""\
    [Log]
    sLogFileName = /home/next/previous.log
    bConfirmQuit = TRUE

    [Memory]
    nMemoryBankSize0 = 32
    nMemoryBankSize1 = 32
    nMemoryBankSize2 = 32
    nMemoryBankSize3 = 32

    [System]
    nMachineType = 1
    bColor = FALSE
    bTurbo = TRUE
    bNBIC = TRUE
    nSCSI = TRUE
    nRTC = TRUE
    nCpuLevel = 4
    nCpuFreq = 33
    bDSPMemoryExpansion = TRUE
    n_FPUType = 68040

    [Dimension]
    nConsoleSlot = 2
    bEnabled0 = TRUE
    nMemoryBankSize00 = 16
    nMemoryBankSize01 = 16

    [HardDisk]
    szImageName0 = /home/next/nextstep/NS33.dd
    bDiskInserted0 = TRUE
    """)


@pytest.fixture
def machine(tmp_path, monkeypatch):
    """A fake emulator that can be told how it behaves after a change."""
    class Emulator:
        def __init__(self):
            self.running = True
            self.age = 3600
            self.powered_off = 0

        def emulator_is_running(self):
            return self.running

        def emulator_uptime_seconds(self):
            return self.age if self.running else None

        def press_power(self):
            self.powered_off += 1
            self.running = False
            return True

        def comes_back(self, age=3600):
            """What the console does once the hold is off."""
            self.running = True
            self.age = age

    emulator = Emulator()
    monkeypatch.setattr(kiosk, "emulator_is_running", emulator.emulator_is_running)
    monkeypatch.setattr(kiosk, "emulator_uptime_seconds", emulator.emulator_uptime_seconds)
    monkeypatch.setattr(kiosk, "press_power", emulator.press_power)
    return emulator


@pytest.fixture
def settings(tmp_path):
    from conftest import settings_for
    path = tmp_path / "previous.cfg"
    path.write_text(REAL_SHAPE)
    return settings_for(tmp_path, previous_config=path, runtime_directory=tmp_path)


def run(identifier, settings, machine, back_as=3600, come_back=True):
    """Runs a change, with the emulator returning as told."""
    steps = []

    def sleep(_seconds):
        steps.append("waited")
        # The hold coming off is what lets the console start it again, so the
        # emulator returns at the first wait after that.
        if come_back and not machine.running and not kiosk.is_held(settings.runtime_directory):
            machine.comes_back(back_as)

    return change.to_machine(identifier, settings, sleep=sleep)


# -- the ordinary case ---------------------------------------------------


def test_a_machine_is_written_and_comes_back(settings, machine):
    finished, reason = run("nextstation-turbo-color", settings, machine)

    assert finished is True
    assert "NeXTstation Turbo Color" in reason
    assert config.read(settings.previous_config)["machine"] == "NeXTstation Turbo"
    assert machine.powered_off == 1


def test_the_guest_is_shut_down_before_anything_is_written(settings, machine):
    """Previous writes previous.cfg from memory when it exits, so a change made
    underneath a running emulator is thrown away by the emulator itself."""
    written = []
    original = config.write

    def watch(path, values):
        written.append(machine.running)
        return original(path, values)

    import unittest.mock
    with unittest.mock.patch.object(config, "write", watch):
        run("nextstation", settings, machine)

    assert written == [False]


def test_the_rest_of_the_file_is_untouched(settings, machine):
    before = settings.previous_config.read_text().splitlines()
    run("next-computer", settings, machine)
    after = settings.previous_config.read_text().splitlines()

    assert len(before) == len(after)
    # The disk it boots from is not the machine's business and must survive.
    assert "szImageName0 = /home/next/nextstep/NS33.dd" in after
    assert "bDiskInserted0 = TRUE" in after


def test_the_previous_file_is_kept_beside_it(settings, machine):
    before = settings.previous_config.read_text()
    run("nextstation", settings, machine)

    backup = settings.previous_config.with_suffix(".cfg.bak")
    assert backup.exists()
    assert backup.read_text() == before


def test_choosing_what_is_already_set_changes_nothing(settings, machine):
    before = settings.previous_config.read_text()
    finished, reason = run("nextcube-turbo-dimension", settings, machine)

    assert finished is True
    assert "war schon eingestellt" in reason
    assert settings.previous_config.read_text() == before


# -- when it does not come back ------------------------------------------


def test_a_machine_that_never_returns_is_rolled_back(settings, machine):
    """The one outcome this feature must not produce is a black screen with
    SSH as the only way back."""
    before = settings.previous_config.read_text()

    finished, reason = run("nextstation", settings, machine, come_back=False)

    assert finished is False
    assert "kam nicht hoch" in reason
    assert settings.previous_config.read_text() == before


def test_a_machine_that_restarts_over_and_over_counts_as_not_coming_back(settings, machine):
    """A configuration Previous cannot run makes it exit at once, and the
    waiting console starts it again. Asking only whether something is running
    would see that loop and call it success."""
    before = settings.previous_config.read_text()

    finished, reason = run("nextstation", settings, machine, back_as=1)

    assert finished is False
    assert "kam nicht hoch" in reason
    assert settings.previous_config.read_text() == before


def test_a_name_that_is_not_a_machine_changes_nothing(settings, machine):
    before = settings.previous_config.read_text()

    finished, reason = run("amiga-2000", settings, machine)

    assert finished is False
    assert "keine Maschine" in reason
    assert settings.previous_config.read_text() == before
    # And nothing was switched off for it.
    assert machine.powered_off == 0


def test_a_guest_that_will_not_shut_down_leaves_the_file_alone(settings, machine):
    """Writing underneath a running emulator loses the change when it exits."""
    before = settings.previous_config.read_text()
    machine.press_power = lambda: True   # key sent, guest ignores it

    import unittest.mock
    with unittest.mock.patch.object(kiosk, "press_power", machine.press_power):
        finished, reason = change.to_machine(
            "nextstation", settings, sleep=lambda _s: None)

    assert finished is False
    assert "shutting down" in reason
    assert settings.previous_config.read_text() == before
