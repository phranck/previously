"""Reading previous.cfg.

The fixtures are cut from a file the emulator actually wrote, so the shape
being tested is the shape that exists rather than the one that would be
convenient.
"""

import textwrap

import pytest

from previously import config

CUBE_TURBO_WITH_DIMENSION = textwrap.dedent("""
    [System]
    nMachineType = 1
    bColor = FALSE
    bTurbo = TRUE
    nCpuLevel = 4
    nCpuFreq = 33

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
    nCpuLevel = 1
    nCpuFreq = 25

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
