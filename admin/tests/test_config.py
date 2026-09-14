"""Reading previous.cfg.

The fixtures are cut from a file the emulator actually wrote, so the shape
being tested is the shape that exists rather than the one that would be
convenient.
"""

import os
import textwrap

import pytest

from previously import config

CUBE_TURBO_WITH_DIMENSION = textwrap.dedent("""
    [System]
    nMachineType = 1
    bColor = FALSE
    bTurbo = TRUE
    bNBIC = TRUE
    nSCSI = TRUE
    nRTC = TRUE
    nCpuLevel = 4
    nCpuFreq = 33
    n_FPUType = 68040

    [Memory]
    nMemoryBankSize0 = 32
    nMemoryBankSize1 = 32
    nMemoryBankSize2 = 32
    nMemoryBankSize3 = 32

    [HardDisk]
    szImageName0 = /home/next/nextstep/NS33_2GB.dd
    nDeviceType0 = 1
    bDiskInserted0 = TRUE
    szImageName1 = /home/next/
    bDiskInserted1 = FALSE

    [Dimension]
    bEnabled0 = TRUE
    """)

PLAIN_STATION = textwrap.dedent("""
    [System]
    nMachineType = 2
    bColor = TRUE
    bTurbo = FALSE
    bNBIC = FALSE
    nSCSI = TRUE
    nRTC = TRUE
    nCpuLevel = 1
    nCpuFreq = 25
    n_FPUType = 68040

    [Memory]
    nMemoryBankSize0 = 16
    nMemoryBankSize1 = 16
    nMemoryBankSize2 = 0
    nMemoryBankSize3 = 0

    [HardDisk]
    bDiskInserted0 = FALSE

    [Dimension]
    bEnabled0 = FALSE
    """)


def write(tmp_path, text):
    path = tmp_path / "previous.cfg"
    path.write_text(text)
    return path


def test_reads_a_cube_turbo_with_a_dimension(tmp_path):
    answer = config.read(write(tmp_path, CUBE_TURBO_WITH_DIMENSION))

    assert answer["machine"] == "NeXTcube Turbo mit NeXTdimension"
    assert answer["cpu"] == "68040, 33 MHz"
    assert answer["memory_mb"] == 128
    assert answer["disk"] == "NS33_2GB.dd"
    assert answer["dimension"] is True


def test_a_seated_dimension_means_colour(tmp_path):
    """A cube has no colour of its own, so the board is what decides it."""
    answer = config.read(write(tmp_path, CUBE_TURBO_WITH_DIMENSION))
    assert answer["screen"] == "NeXTdimension, farbig"


def test_reads_a_station_without_one(tmp_path):
    answer = config.read(write(tmp_path, PLAIN_STATION))

    assert answer["machine"] == "NeXTstation"
    assert answer["memory_mb"] == 32
    assert answer["screen"] == "MegaPixel, farbig"
    assert answer["dimension"] is False


def test_a_cube_is_reported_as_a_cube(tmp_path):
    """The interface draws the machine the boot ROM draws, and this is what
    tells it which of the two pictures that is."""
    assert config.read(write(tmp_path, CUBE_TURBO_WITH_DIMENSION))["enclosure"] == "cube"


def test_a_station_is_reported_as_a_station(tmp_path):
    assert config.read(write(tmp_path, PLAIN_STATION))["enclosure"] == "station"


def test_the_1988_machine_stands_in_the_cube_case(tmp_path):
    """NeXT built the NeXT Computer and the NeXTcube in the same case, so the
    ROM has one picture for both."""
    answer = config.read(write(tmp_path, "[System]\nnMachineType = 0\n"))
    assert answer["enclosure"] == "cube"


def test_a_machine_type_nobody_knows_still_answers():
    """A page that draws nothing tells the reader less than one that draws the
    machine NeXT built first."""
    assert config.enclosure(99) == "cube"


def test_no_inserted_disk_reads_as_none(tmp_path):
    assert config.read(write(tmp_path, PLAIN_STATION))["disk"] is None


# -- describing a machine from either side -------------------------------


def test_the_catalogue_and_the_file_describe_a_machine_the_same_way(tmp_path):
    """The shelf says what a machine would be and the info window says what
    the running one is. Two ways of working that out would drift."""
    from previously import machines

    machine = machines.find("nextstation-turbo-color")
    settings = machines.settings_for(machine)
    from_catalogue = config.describe(
        settings["System"], settings["Memory"], settings["Dimension"])

    path = write(tmp_path, PLAIN_STATION)
    config.write(path, settings)
    from_file = config.read(path)
    del from_file["disk"]

    assert from_file == from_catalogue


def test_the_three_chips_are_named(tmp_path):
    """They are what a machine is made of, and getting one wrong is what makes
    a configuration reset for ever instead of booting."""
    turbo = config.read(write(tmp_path, CUBE_TURBO_WITH_DIMENSION))
    assert turbo["chips"] == "MCCS1850, NCR53C90A, mit NeXTbus"


def test_a_machine_without_those_chips_says_the_others(tmp_path):
    plain = config.read(write(tmp_path, textwrap.dedent("""
        [System]
        nMachineType = 2
        bTurbo = FALSE
        nRTC = FALSE
        nSCSI = TRUE
        bNBIC = FALSE
        """)))
    assert plain["chips"] == "MC68HC68T1, NCR53C90A, ohne NeXTbus"


# -- which of the eleven the file is -------------------------------------


def catalogue():
    """@returns The eleven as matching() wants them."""
    from previously import machines
    return [(machine.identifier, machines.settings_for(machine))
            for machine in machines.CATALOGUE]


def test_a_file_written_from_the_catalogue_is_recognised(tmp_path):
    from previously import machines

    path = write(tmp_path, "[System]\n")
    config.write(path, machines.settings_for(machines.find("nextstation-color")))

    assert config.matching(path, catalogue()) == "nextstation-color"


def test_a_nitro_is_told_apart_from_the_machine_it_is_named_after(tmp_path):
    """Previous has no idea of Nitro, so the file calls this one NeXTcube
    Turbo. Matching against the whole catalogue is what tells them apart, and
    matching against the name alone would not."""
    from previously import machines

    path = write(tmp_path, "[System]\n")
    config.write(path, machines.settings_for(machines.find("nextcube-turbo-nitro")))

    assert config.read(path)["machine"] == "NeXTcube Turbo"
    assert config.matching(path, catalogue()) == "nextcube-turbo-nitro"


def test_a_machine_somebody_put_together_is_none_of_them(tmp_path):
    """One bank changed by hand, and it is no longer any of the eleven. That
    is not an error: it is a machine this tool does not offer, and it must not
    be presented as one that it does."""
    from previously import machines

    path = write(tmp_path, "[System]\n")
    config.write(path, machines.settings_for(machines.find("nextcube-turbo")))
    path.write_text(path.read_text().replace(
        "nMemoryBankSize0 = 32", "nMemoryBankSize0 = 8"))

    assert config.matching(path, catalogue()) is None


def test_what_differs_is_named(tmp_path):
    from previously import machines

    path = write(tmp_path, "[System]\n")
    settings = machines.settings_for(machines.find("nextcube-turbo"))
    config.write(path, settings)
    path.write_text(path.read_text().replace(
        "nMemoryBankSize0 = 32", "nMemoryBankSize0 = 8"))

    assert config.differences(path, settings) == {
        "Memory": {"nMemoryBankSize0": ("8", "32")}}


def test_a_file_missing_a_key_differs_by_it(tmp_path):
    """Previous writes every key it knows, so a file without one has been
    edited, and it is not the machine it claims to be."""
    from previously import machines

    settings = machines.settings_for(machines.find("nextstation"))
    path = write(tmp_path, "[System]\nnMachineType = 2\n")

    differing = config.differences(path, settings)

    assert differing["System"]["bTurbo"] == (None, "FALSE")
    assert "nMachineType" not in differing.get("System", {})


# -- who wrote the file --------------------------------------------------


def test_a_file_this_service_wrote_is_recognised(tmp_path):
    path = write(tmp_path, PLAIN_STATION)
    state = tmp_path / "state"
    state.mkdir()

    assert config.note_written(path, state) is True
    assert config.file_state(path, None, state_directory=state)["written_by_us"] is True


def test_a_file_somebody_else_wrote_is_not(tmp_path):
    """Previous's own dialogue and a text editor look alike from here, so the
    answer is only ever yes or not-us."""
    path = write(tmp_path, PLAIN_STATION)
    state = tmp_path / "state"
    state.mkdir()
    config.note_written(path, state)

    path.write_text(PLAIN_STATION + "\nbTurbo = TRUE\n")

    assert config.file_state(path, None, state_directory=state)["written_by_us"] is False


def test_without_a_note_nothing_is_claimed(tmp_path):
    path = write(tmp_path, PLAIN_STATION)
    state = tmp_path / "state"
    state.mkdir()

    assert config.file_state(path, None, state_directory=state)["written_by_us"] is False


def test_a_note_that_cannot_be_kept_is_not_an_error(tmp_path):
    """The file was written either way, and all that is lost is being able to
    say later who wrote it."""
    path = write(tmp_path, PLAIN_STATION)

    assert config.note_written(path, tmp_path / "no-such-directory") is False


# -- the file against the machine that is running ------------------------


def test_a_file_written_after_the_emulator_started_has_not_been_tried(tmp_path):
    """Previous reads the file when it starts and never again, so this is the
    only place the difference between the two can be seen."""
    path = write(tmp_path, PLAIN_STATION)
    os.utime(path, (1_000_500, 1_000_500))

    state = config.file_state(path, emulator_age_seconds=100, now=1_000_550)

    assert state["changed_at"] == 1_000_500
    assert state["newer_than_the_machine"] is True


def test_a_file_older_than_the_emulator_is_what_it_is_running(tmp_path):
    path = write(tmp_path, PLAIN_STATION)
    os.utime(path, (1_000_000, 1_000_000))

    state = config.file_state(path, emulator_age_seconds=100, now=1_000_550)

    assert state["newer_than_the_machine"] is False


def test_with_nothing_running_there_is_nothing_to_disagree_with(tmp_path):
    """A file cannot be newer than a machine that is not there."""
    path = write(tmp_path, PLAIN_STATION)

    state = config.file_state(path, emulator_age_seconds=None)

    assert state["newer_than_the_machine"] is False
    assert state["changed_at"] is not None


def test_a_file_that_is_not_there_says_so_rather_than_raising(tmp_path):
    state = config.file_state(tmp_path / "absent.cfg", emulator_age_seconds=100)

    assert state["changed_at"] is None
    assert state["newer_than_the_machine"] is False


def test_a_missing_file_is_refused(tmp_path):
    with pytest.raises(config.NotReadable):
        config.read(tmp_path / "absent.cfg")


def test_something_that_is_not_a_config_is_refused(tmp_path):
    path = tmp_path / "previous.cfg"
    path.write_bytes(b"\x00\x01 this is a disk image, not a config")
    with pytest.raises(config.NotReadable):
        config.read(path)


def test_a_config_missing_sections_still_answers(tmp_path):
    """Previous writes every section, but a hand-edited file may not, and a
    page that shows nothing is better than one that fails."""
    answer = config.read(write(tmp_path, "[System]\nnMachineType = 0\n"))

    assert answer["machine"] == "NeXT Computer"
    assert answer["memory_mb"] == 0
    assert answer["disk"] is None


def test_the_turbo_name_is_not_given_to_a_machine_that_had_none(tmp_path):
    """NeXT built no turbo of the 1988 machine, so the flag is meaningless
    there and must not reach the name."""
    answer = config.read(write(tmp_path, textwrap.dedent("""
        [System]
        nMachineType = 0
        bTurbo = TRUE
        """)))
    assert answer["machine"] == "NeXT Computer"
