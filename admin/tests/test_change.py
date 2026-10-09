"""Changing the machine, and what happens when it will not come back.

The fixture is a real previous.cfg, cut from the one on the machine, so what is
tested is the file that exists rather than one shaped to be convenient.
"""

import configparser
import pathlib
import re
import textwrap

import pytest

from previously import change, config, discs, kiosk, saved, screen

REAL_SHAPE = textwrap.dedent("""\
    [Log]
    sLogFileName = /home/next/previous.log
    bConfirmQuit = TRUE

    [Screen]
    nMode = 0
    nSingleModeSlot = 2
    bFullScreen = TRUE
    bShowStatusbar = FALSE
    bShowTitlebar = FALSE

    [Memory]
    nMemoryBankSize0 = 32
    nMemoryBankSize1 = 32
    nMemoryBankSize2 = 32
    nMemoryBankSize3 = 32
    nMemorySpeed = 1

    [System]
    nMachineType = 1
    bColor = FALSE
    bTurbo = TRUE
    bNBIC = TRUE
    nSCSI = TRUE
    nRTC = TRUE
    nCpuLevel = 4
    nCpuFreq = 33
    nDSPType = 2
    bDSPMemoryExpansion = TRUE
    n_FPUType = 68040

    [Dimension]
    nConsoleSlot = 2
    bEnabled0 = TRUE
    nMemoryBankSize00 = 16
    nMemoryBankSize01 = 16
    nMemoryBankSize02 = 0
    nMemoryBankSize03 = 0
    bEnabled1 = FALSE
    nMemoryBankSize10 = 0
    nMemoryBankSize11 = 0
    nMemoryBankSize12 = 0
    nMemoryBankSize13 = 0
    bEnabled2 = FALSE
    nMemoryBankSize20 = 0
    nMemoryBankSize21 = 0
    nMemoryBankSize22 = 0
    nMemoryBankSize23 = 0

    [MagnetoOptical]
    bDriveConnected0 = FALSE
    bDriveConnected1 = FALSE

    [Floppy]
    bDriveConnected0 = TRUE
    bDriveConnected1 = FALSE
    bDriveConnected2 = FALSE
    bDriveConnected3 = FALSE

    [Ethernet]
    bEthernetConnected = TRUE
    bTwistedPair = FALSE

    [Printer]
    bPrinterConnected = FALSE

    [HardDisk]
    szImageName0 = /home/next/nextstep/NS33.dd
    nDeviceType0 = 1
    bDiskInserted0 = TRUE
    bWriteProtected0 = FALSE
    szImageName1 = /home/next/discs/DeveloperTools.iso
    nDeviceType1 = 2
    bDiskInserted1 = TRUE
    bWriteProtected1 = TRUE
    nWriteProtection = 0
    """)


@pytest.fixture
def machine(tmp_path, monkeypatch):
    """A fake emulator that can be told how it behaves after a change."""
    class Emulator:
        def __init__(self):
            self.running = True
            self.age = 3600
            self.powered_off = 0
            #: What the screen says now, and what it will say once the
            #: machine has been changed. They differ because the machine
            #: being left behind was running: only the new one is in
            #: question.
            self.screen = True
            self.screen_after = True
            #: How many looks at the new machine find nothing yet, which is
            #: a NeXTdimension whose processor is still coming up.
            self.dark_looks = 0
            self.came_back = False
            self.quit_asked = 0

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
            self.screen = self.screen_after
            self.came_back = True

        def looks(self):
            """What reading the screen answers."""
            if self.came_back and self.dark_looks > 0:
                self.dark_looks -= 1
                return False
            return self.screen

        def quit(self, sleep=None):
            """Previous being told to go, for a guest that never started."""
            self.quit_asked += 1
            self.running = False
            return True

    emulator = Emulator()
    monkeypatch.setattr(kiosk, "emulator_is_running", emulator.emulator_is_running)
    monkeypatch.setattr(kiosk, "emulator_uptime_seconds", emulator.emulator_uptime_seconds)
    monkeypatch.setattr(kiosk, "press_power", emulator.press_power)
    # No X server in a test, so the screen cannot be read and nothing is
    # claimed about it. A test that is about the screen says so itself.
    monkeypatch.setattr(screen, "looks_alive", emulator.looks)
    monkeypatch.setattr(kiosk, "quit_emulator", emulator.quit)
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
    finished, told = run("nextstation-turbo-color", settings, machine)

    assert finished is True
    assert told["machine"] == "NeXTstation Turbo Color"
    # What the file says about itself, which cannot carry the Nitro or the
    # color that the catalog's own name does.
    written = config.read(settings.previous_config)
    assert written["model"] == "NeXTstation"
    assert written["turbo"] is True
    assert written["colour"] is True
    assert machine.powered_off == 1


def test_the_guest_is_shut_down_before_anything_is_written(settings, machine):
    """Previous reads previous.cfg only when it starts, so the guest goes down
    properly first and the new machine is the one that comes back."""
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
    finished, told = run("nextcube-turbo-dimension", settings, machine)

    assert finished is True
    assert told["reason"] == "machine.was-already-set"
    assert settings.previous_config.read_text() == before


# -- when it does not come back ------------------------------------------


def test_a_machine_that_shows_nothing_is_rolled_back(settings, machine):
    """The emulator running is not the machine running. A configuration
    Previous cannot make sense of leaves the process up and the screen blank,
    and that looked like success until the screen was read."""
    before = settings.previous_config.read_text()
    machine.screen_after = False

    finished, told = run("nextstation", settings, machine)

    assert finished is False
    assert told["why"] == "blank"
    assert settings.previous_config.read_text() == before


def test_a_blank_machine_is_got_out_of_the_way(settings, machine):
    """Previous reads its configuration once, at startup, so putting the file
    back underneath it changes nothing until it goes. The power key cannot do
    it: NeXTSTEP never started, so there is nothing there to answer."""
    machine.screen_after = False

    run("nextstation", settings, machine)

    assert machine.quit_asked == 1
    assert machine.powered_off == 1


def test_a_machine_that_shows_something_is_left_alone(settings, machine):
    machine.screen_after = True

    finished, told = run("nextstation", settings, machine)

    assert finished is True
    assert machine.quit_asked == 0
    assert told["reason"] == "machine.running"


def test_a_screen_that_cannot_be_read_is_not_held_against_it(settings, machine):
    """Without an X server, or without the tool that reads it, every machine
    would otherwise look broken."""
    machine.screen = None
    machine.screen_after = None

    finished, _ = run("nextstation", settings, machine)

    assert finished is True
    assert machine.quit_asked == 0


def test_a_machine_with_a_board_is_given_time_to_draw(settings, machine):
    """A NeXTdimension draws nothing until its own processor is up, which takes
    minutes rather than the seconds a machine without one needs. Read once
    after ten seconds, every switch to one was put back."""
    machine.dark_looks = 60

    finished, told = run("nextcube-dimension", settings, machine)

    assert finished is True, told
    assert told["reason"] == "machine.running"
    assert machine.quit_asked == 0


def test_a_machine_with_a_board_that_never_draws_is_rolled_back(settings, machine):
    before = settings.previous_config.read_text()
    machine.dark_looks = change.DIMENSION_PICTURE_SECONDS + 1

    finished, told = run("nextcube-dimension", settings, machine)

    assert finished is False
    assert told["why"] == "blank"
    assert settings.previous_config.read_text() == before


def test_a_machine_without_a_board_is_looked_at_once(settings, machine):
    """It has drawn its boot panel by the time it has settled, so a blank
    screen then is a machine that will not come up, and waiting minutes for it
    only keeps somebody from their machine."""
    machine.dark_looks = 1

    finished, told = run("nextcube-turbo", settings, machine)

    assert finished is False
    assert told["why"] == "blank"


def test_a_machine_with_a_board_is_shown_on_it(settings, machine):
    """Previous shows the CPU board's own screen unless the file says
    otherwise, and the console of a machine with a NeXTdimension is on the
    board. A file that names no screen at all is what the Pi had."""
    settings.previous_config.write_text(
        REAL_SHAPE.replace("nMode = 0\n", "").replace("nSingleModeSlot = 2\n", ""))

    run("nextcube-dimension", settings, machine)

    written = configparser.ConfigParser()
    written.optionxform = str
    written.read(settings.previous_config)
    assert written["Screen"]["nMode"] == "0"
    assert written["Screen"]["nSingleModeSlot"] == "2"
    assert written["Screen"]["bFullScreen"] == "TRUE"


def test_the_browser_waits_longer_than_the_longest_change():
    """The page gives up on an answer after a fixed time, and a change that
    is still running then is reported as a service that cannot be reached."""
    source = pathlib.Path(__file__).resolve().parent.parent / "interface" / "app" / "service.js"
    found = re.search(r"const OPERATION_TIMEOUT_MS = (\d+);", source.read_text())

    assert found, "OPERATION_TIMEOUT_MS is not where this test looks for it"
    assert int(found.group(1)) > change.LONGEST_SECONDS * 1000


def test_a_machine_that_never_returns_is_rolled_back(settings, machine):
    """The one outcome this feature must not produce is a black screen with
    SSH as the only way back."""
    before = settings.previous_config.read_text()

    finished, told = run("nextstation", settings, machine, come_back=False)

    assert finished is False
    assert told["why"] == "never-came-up"
    assert settings.previous_config.read_text() == before


def test_a_machine_that_restarts_over_and_over_counts_as_not_coming_back(settings, machine):
    """A configuration Previous cannot run makes it exit at once, and the
    waiting console starts it again. Asking only whether something is running
    would see that loop and call it success."""
    before = settings.previous_config.read_text()

    finished, told = run("nextstation", settings, machine, back_as=1)

    assert finished is False
    assert told["why"] == "never-came-up"
    assert settings.previous_config.read_text() == before


def test_a_name_that_is_not_a_machine_changes_nothing(settings, machine):
    before = settings.previous_config.read_text()

    finished, told = run("amiga-2000", settings, machine)

    assert finished is False
    assert told["reason"] == "machine.no-such"
    assert settings.previous_config.read_text() == before
    # And nothing was switched off for it.
    assert machine.powered_off == 0


def test_a_guest_that_will_not_shut_down_leaves_the_file_alone(settings, machine):
    """A file written underneath a guest that will not go down would describe a
    machine nobody has tried, so nothing is written."""
    before = settings.previous_config.read_text()
    machine.press_power = lambda: True   # key sent, guest ignores it

    import unittest.mock
    with unittest.mock.patch.object(kiosk, "press_power", machine.press_power):
        finished, told = change.to_machine(
            "nextstation", settings, sleep=lambda _s: None)

    assert finished is False
    assert told["reason"] == "guest.still-shutting-down"
    assert settings.previous_config.read_text() == before


# -- which disk the machine boots ----------------------------------------


@pytest.fixture
def disks(settings):
    """Two systems on the card, and the configuration booting neither of them.

    Neither, because the fixture's file points at a disk this folder does not
    hold, which is the state of a machine that was set up by `install.sh`.
    """
    where = settings.disks
    where.mkdir(parents=True, exist_ok=True)
    (where / "nextstep-3.3.dd").write_bytes(b"a system")
    (where / "openstep-4.2.dd").write_bytes(b"another")
    return where


def boot(identifier, settings, machine, come_back=True):
    """Makes the machine boot a disk, with the emulator returning as told."""
    def sleep(_seconds):
        if come_back and not machine.running \
                and not kiosk.is_held(settings.runtime_directory):
            machine.comes_back()

    return change.to_disk(identifier, settings, sleep=sleep)


def test_a_disk_is_written_and_the_machine_comes_back(settings, machine, disks):
    finished, told = boot("openstep-4.2", settings, machine)

    assert finished is True
    assert told["reason"] == "disk.booting"
    assert told["machine"] == "OPENSTEP 4.2"
    assert machine.powered_off == 1
    assert config.booting_from(settings.previous_config) \
        == str(disks / "openstep-4.2.dd")


def test_nothing_in_that_section_is_written_but_the_three_keys(settings, machine, disks):
    """The README says this tool leaves the disks, the sound, the network and
    the screen exactly as the file has them, and this is the one exception to
    it. A disc somebody put on the second slot is still on it afterwards, and
    so is everything else in that section."""
    before = settings.previous_config.read_text().splitlines()

    boot("nextstep-3.3", settings, machine)

    after = settings.previous_config.read_text().splitlines()
    differ = [line for line in after if line not in before]

    assert sorted(differ) == sorted([
        "szImageName0 = %s" % (disks / "nextstep-3.3.dd"),
    ])
    # The three that were already what they will be, said out loud because they
    # are the other two thirds of what this writes.
    assert "nDeviceType0 = 1" in after
    assert "bDiskInserted0 = TRUE" in after
    # And the disc on the slot beside it, which is none of this tool's business.
    assert "szImageName1 = /home/next/discs/DeveloperTools.iso" in after
    assert "bWriteProtected1 = TRUE" in after
    assert "nWriteProtection = 0" in after
    assert len(before) == len(after)


def test_the_guest_goes_down_before_a_disk_is_swapped(settings, machine, disks):
    """A disk changed underneath a running system is a torn file system, which
    is what pulling the plug does."""
    written = []
    original = config.write

    def watch(path, values):
        written.append(machine.running)
        return original(path, values)

    import unittest.mock
    with unittest.mock.patch.object(config, "write", watch):
        boot("nextstep-3.3", settings, machine)

    assert written == [False]


def test_a_disk_that_does_not_come_back_is_put_straight_back(settings, machine, disks):
    """Which system runs on which machine is not written down anywhere this
    tool can read, so what answers it is the machine itself: it is tried, and
    a machine that does not come up gets its old disk back."""
    before = settings.previous_config.read_text()

    finished, told = boot("openstep-4.2", settings, machine, come_back=False)

    assert finished is False
    assert told["why"] == "never-came-up"
    assert settings.previous_config.read_text() == before


def test_a_blank_screen_after_a_swap_is_rolled_back_too(settings, machine, disks):
    before = settings.previous_config.read_text()
    machine.screen_after = False

    finished, told = boot("openstep-4.2", settings, machine)

    assert finished is False
    assert told["why"] == "blank"
    assert told["machine"] == "OPENSTEP 4.2"
    assert settings.previous_config.read_text() == before


def test_a_system_that_is_not_on_the_card_changes_nothing(settings, machine, disks):
    before = settings.previous_config.read_text()

    finished, told = boot("nextstep-2.2", settings, machine)

    assert finished is False
    assert told["reason"] == "disk.not-here"
    assert told["name"] == "NeXTSTEP 2.2"
    assert settings.previous_config.read_text() == before
    assert machine.powered_off == 0


def test_a_name_that_is_not_a_system_changes_nothing(settings, machine, disks):
    finished, told = boot("nextstep-9.9", settings, machine)

    assert finished is False
    assert told["reason"] == "disk.no-such"
    assert machine.powered_off == 0


def test_booting_the_disk_that_is_already_booting_changes_nothing(settings, machine, disks):
    boot("nextstep-3.3", settings, machine)
    before = settings.previous_config.read_text()

    finished, told = boot("nextstep-3.3", settings, machine)

    assert finished is True
    assert told["reason"] == "disk.was-already-set"
    assert settings.previous_config.read_text() == before


# -- what goes beside the system -----------------------------------------


@pytest.fixture
def media(settings):
    """A disc somebody has put on the Pi, and one that says it is ISO 9660."""
    where = discs.folder(settings.disks)
    where.mkdir(parents=True, exist_ok=True)
    (where / "DeveloperTools.img").write_bytes(b"not an iso")

    an_iso = where / "SomethingElse.iso"
    an_iso.write_bytes(b"\0" * discs.ISO_AT + discs.ISO_SIGNATURE)
    return where


def put_in(name, settings, machine):
    """Puts a disc in, with the emulator returning as told."""
    def sleep(_seconds):
        if not machine.running and not kiosk.is_held(settings.runtime_directory):
            machine.comes_back()

    return change.to_disc(name, settings, sleep=sleep)


def test_a_disc_goes_on_a_free_slot_beside_the_disk(settings, machine, media):
    """The machine boots slot 0 and everything else is the bus. The fixture
    already holds a disc on slot 1, so the first free one is the third, and
    neither of the two before it is touched."""
    finished, told = put_in("DeveloperTools.img", settings, machine)

    assert finished is True
    assert told["reason"] == "disc.inserted"
    written = config.slots(settings.previous_config)
    assert written[2]["image"] == str(media / "DeveloperTools.img")
    # Read only, because that is what a disc is, and Previous makes a CD target
    # read only from its type alone.
    assert written[2]["type"] == int(discs.CD)
    assert written[2]["inserted"] is True
    # The disk the machine boots, and the disc that was already on the bus.
    assert written[0]["image"] == "/home/next/nextstep/NS33.dd"
    assert written[1]["image"] == "/home/next/discs/DeveloperTools.iso"


def test_a_disc_that_is_not_on_this_machine_changes_nothing(settings, machine, media):
    before = settings.previous_config.read_text()

    finished, told = put_in("NothingOfThatName.iso", settings, machine)

    assert finished is False
    assert told["reason"] == "disc.no-such"
    assert settings.previous_config.read_text() == before
    assert machine.powered_off == 0


@pytest.mark.parametrize("named", ["../../etc/passwd", "/etc/passwd", ""])
def test_a_name_that_is_a_path_asks_for_a_file_that_is_not_there(
        settings, machine, media, named):
    """The name is matched against the listing of one folder rather than joined
    onto a path, so nothing that arrives from a browser reaches the filesystem
    as a path."""
    finished, told = put_in(named, settings, machine)

    assert finished is False
    assert told["reason"] == "disc.no-such"


def test_a_bus_with_no_room_on_it_says_so(settings, machine, media, monkeypatch):
    monkeypatch.setattr(config, "free_slot", lambda path: None)
    before = settings.previous_config.read_text()

    finished, told = put_in("DeveloperTools.img", settings, machine)

    assert finished is False
    assert told["reason"] == "disc.no-free-slot"
    assert settings.previous_config.read_text() == before


def test_a_disc_can_be_taken_out_again(settings, machine, media):
    def sleep(_seconds):
        if not machine.running and not kiosk.is_held(settings.runtime_directory):
            machine.comes_back()

    finished, told = change.eject_disc(1, settings, sleep=sleep)

    assert finished is True
    assert told["reason"] == "disc.ejected"
    assert told["machine"] == "DeveloperTools.iso"
    written = config.slots(settings.previous_config)
    assert written[1]["inserted"] is False
    assert written[1]["type"] == 0


def test_the_disk_the_machine_boots_is_not_a_disc(settings, machine):
    """Slot 0 is the system. Taking it out from under NeXTSTEP is not ejecting
    a disc, it is pulling the disk out of a running machine."""
    before = settings.previous_config.read_text()

    finished, told = change.eject_disc(0, settings, sleep=lambda _s: None)

    assert finished is False
    assert told["reason"] == "disc.that-is-the-disk"
    assert settings.previous_config.read_text() == before
    assert machine.powered_off == 0


@pytest.mark.parametrize("slot", [-1, 7, 99, None, "1"])
def test_a_slot_that_is_not_one_of_the_seven_is_refused(settings, machine, slot):
    finished, told = change.eject_disc(slot, settings, sleep=lambda _s: None)

    assert finished is False
    assert told["reason"] == "disc.no-such-slot"


def test_a_slot_with_nothing_on_it_is_not_ejected(settings, machine):
    finished, told = change.eject_disc(3, settings, sleep=lambda _s: None)

    assert finished is False
    assert told["reason"] == "disc.nothing-there"
    assert machine.powered_off == 0


def test_the_guest_goes_down_before_a_disc_arrives(settings, machine, media):
    """Previous reads its configuration when it starts and never again, so a
    disc written into that file arrives when the machine next comes up. Its own
    dialog can do it without a reset; a file written from outside cannot."""
    written = []
    original = config.write

    def watch(path, values):
        written.append(machine.running)
        return original(path, values)

    import unittest.mock
    with unittest.mock.patch.object(config, "write", watch):
        put_in("DeveloperTools.img", settings, machine)

    assert written == [False]


def test_an_image_that_says_iso_9660_is_known_for_one(settings, media):
    """NeXT's own discs carry a variation of 4.3BSD FFS, so an ISO 9660 image
    mounts nowhere however good it is. The interface says so before somebody
    waits for a machine to come back with nothing new in it."""
    assert discs.is_iso_9660(media / "SomethingElse.iso") is True
    assert discs.is_iso_9660(media / "DeveloperTools.img") is False
    assert discs.is_iso_9660(media / "never-written.iso") is False


# -- a configuration somebody saved --------------------------------------


def test_a_saved_configuration_can_be_activated(settings, machine):
    """The eleven are looked up first and this list second, so a saved
    configuration is reached by the same route and the same double click."""
    finished, _ = saved.save(settings.machines_file, "Meine Kiste", {
        "kind": 2, "turbo": True, "colour": True, "banks": [32, 32, 32, 32]})
    assert finished is True

    finished, told = run("Meine Kiste", settings, machine)

    assert finished is True, told
    assert told["machine"] == "Meine Kiste"
    written = config.read(settings.previous_config)
    assert written["model"] == "NeXTstation"
    assert written["colour"] is True
    assert written["memory_mb"] == 128


def test_a_saved_configuration_is_settled_before_it_is_written(settings, machine):
    """Whatever is in that file, what reaches previous.cfg is a machine the
    emulator will not correct underneath it."""
    saved.save(settings.machines_file, "Ein Kubus", {
        # A cube has no color of its own, and three megabytes is not a size.
        "kind": 1, "colour": True, "banks": [3, 0, 0, 0]})

    finished, _ = run("Ein Kubus", settings, machine)

    assert finished is True
    written = config.read(settings.previous_config)
    assert written["colour"] is False
    assert written["banks"] == [4, 0, 0, 0]


def test_a_file_of_saved_configurations_in_the_way_changes_nothing(settings, machine):
    """It cannot be told whether the name asked for is in there, so nothing is
    switched off and nothing is written."""
    before = settings.previous_config.read_text()
    (settings.machines_file).write_text("{not json at all")

    finished, told = run("Meine Kiste", settings, machine)

    assert finished is False
    assert told["reason"] == "saved.not-readable"
    assert settings.previous_config.read_text() == before
    assert machine.powered_off == 0
