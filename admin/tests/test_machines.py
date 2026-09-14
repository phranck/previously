"""The catalogue, and what each machine is in the file.

The rules being tested are Previous's own, from Configuration_SetSystemDefaults
in its src/configuration.c. Every machine here was booted on the Pi on 14
September 2026 and came up, which is the only test that can really be passed:
a configuration Previous will not run fails silently, with a white screen and
an empty log.
"""

from previously import config, machines


def test_every_identifier_is_used_once():
    identifiers = [machine.identifier for machine in machines.CATALOGUE]
    assert len(identifiers) == len(set(identifiers))


def test_a_machine_is_found_by_its_identifier():
    assert machines.find("nextcube-turbo").name == "NeXTcube Turbo"


def test_something_that_is_not_a_machine_is_not_invented():
    assert machines.find("amiga-2000") is None
    assert machines.find("") is None
    assert machines.find(None) is None


def test_every_machine_sets_the_same_keys():
    """A machine that left a key out would leave the one before it in place,
    which is how a half-changed machine comes about. That is not a tidiness
    point: a machine carrying one chip of a turbo and one of a plain board
    resets for ever and shows a white screen."""
    shapes = set()
    for machine in machines.CATALOGUE:
        settings = machines.settings_for(machine)
        shapes.add(tuple(sorted(
            (section, key)
            for section, keys in settings.items() for key in keys)))
    assert len(shapes) == 1
    assert len(next(iter(shapes))) == 16


def test_the_1988_machine_is_a_68030():
    """NeXT's first machine is a 68030 with a separate 68882, and Previous
    refuses a level that disagrees with the type."""
    system = machines.settings_for(machines.find("next-computer"))["System"]

    assert system["nCpuLevel"] == "3"
    assert system["n_FPUType"] == "68882"
    assert system["nSCSI"] == "FALSE"


def test_everything_after_it_is_a_68040_with_the_unit_on_the_chip():
    for machine in machines.CATALOGUE:
        if machine.identifier == "next-computer":
            continue
        system = machines.settings_for(machine)["System"]
        assert system["nCpuLevel"] == "4", machine.identifier
        assert system["n_FPUType"] == "68040", machine.identifier
        assert system["nSCSI"] == "TRUE", machine.identifier


def test_only_a_turbo_or_a_colour_station_carries_the_later_clock_chip():
    """The MCCS1850 came with the turbo board and with the colour station, and
    a plain machine given it is the machine that would not boot."""
    for machine in machines.CATALOGUE:
        system = machines.settings_for(machine)["System"]
        expected = machine.turbo or (machine.kind == machines.NEXTSTATION and machine.colour)
        assert system["nRTC"] == ("TRUE" if expected else "FALSE"), machine.identifier


def test_the_bus_chip_is_in_the_cubes_and_not_in_the_station():
    """A NeXTstation has no NeXTbus, so it has nothing to interface to it."""
    for machine in machines.CATALOGUE:
        system = machines.settings_for(machine)["System"]
        assert system["bNBIC"] == ("FALSE" if machine.kind == machines.NEXTSTATION else "TRUE"), \
            machine.identifier


def test_the_clock_follows_the_board_rather_than_the_machine():
    for machine in machines.CATALOGUE:
        clock = machines.settings_for(machine)["System"]["nCpuFreq"]
        if machine.nitro:
            assert clock == "40", machine.identifier
        elif machine.turbo:
            assert clock == "33", machine.identifier
        else:
            assert clock == "25", machine.identifier


def test_nitro_is_a_faster_clock_and_nothing_else():
    plain = machines.settings_for(machines.find("nextcube-turbo"))
    nitro = machines.settings_for(machines.find("nextcube-turbo-nitro"))

    assert plain["System"]["nCpuFreq"] == "33"
    assert nitro["System"]["nCpuFreq"] == "40"

    del plain["System"]["nCpuFreq"], nitro["System"]["nCpuFreq"]
    assert plain == nitro


def test_a_seated_board_answers_from_slot_two_and_an_absent_one_from_none():
    """Leaving the slot at what it was would point the machine at a board that
    is no longer there."""
    with_board = machines.settings_for(machines.find("nextcube-dimension"))
    without = machines.settings_for(machines.find("nextcube"))

    assert with_board["Dimension"] == {"bEnabled0": "TRUE", "nConsoleSlot": "2"}
    assert without["Dimension"] == {"bEnabled0": "FALSE", "nConsoleSlot": "0"}


def test_only_the_station_carries_colour_of_its_own():
    """A cube has no colour without a NeXTdimension, and Previous forces the
    flag off for that machine type anyway."""
    for machine in machines.CATALOGUE:
        if machines.settings_for(machine)["System"]["bColor"] == "TRUE":
            assert machine.kind == machines.NEXTSTATION, machine.identifier


def test_only_the_cube_takes_a_dimension():
    """It was a cube board. A station has no slot for it."""
    for machine in machines.CATALOGUE:
        if machine.dimension:
            assert machine.kind == 1, machine.identifier


def test_the_1988_machine_has_no_turbo():
    """NeXT built none, so the flag would be meaningless there."""
    computer = machines.find("next-computer")
    assert computer.turbo is False
    assert machines.settings_for(computer)["System"]["bTurbo"] == "FALSE"


def test_memory_is_four_banks_of_whole_megabytes():
    for machine in machines.CATALOGUE:
        memory = machines.settings_for(machine)["Memory"]
        assert sorted(memory) == ["nMemoryBankSize%d" % i for i in range(4)]
        assert all(value.isdigit() for value in memory.values())


def test_every_machine_has_a_case_the_interface_knows():
    """A machine whose type is missing from the table would silently be drawn
    as a cube, and the shelf would show the wrong picture rather than fail."""
    for machine in machines.CATALOGUE:
        assert machine.kind in config.ENCLOSURES, machine.identifier


def test_every_value_written_is_a_string():
    """A configuration file holds text. An integer here would become one in the
    file through whatever formatting happened to be in the way."""
    for machine in machines.CATALOGUE:
        for keys in machines.settings_for(machine).values():
            assert all(isinstance(value, str) for value in keys.values())
