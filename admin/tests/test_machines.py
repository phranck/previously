"""The catalogue, and what each machine is in the file.

The values were checked against the eleven ready-made configurations in the
project's Papers folder on 13 September 2026, 121 values with no deviation.
Those files are not in this repository, so what is tested here is the rules
that produce them rather than the comparison itself.
"""

from previously import machines


def test_every_identifier_is_used_once():
    identifiers = [machine.identifier for machine in machines.CATALOGUE]
    assert len(identifiers) == len(set(identifiers))


def test_a_machine_is_found_by_its_identifier():
    assert machines.find("nextcube-turbo").name == "NeXTcube Turbo"


def test_something_that_is_not_a_machine_is_not_invented():
    assert machines.find("amiga-2000") is None
    assert machines.find("") is None
    assert machines.find(None) is None


def test_every_machine_sets_the_same_ten_keys():
    """A machine that left a key out would leave the one before it in place,
    which is how a half-changed machine comes about."""
    shapes = set()
    for machine in machines.CATALOGUE:
        settings = machines.settings_for(machine)
        shapes.add(tuple(sorted(
            (section, key)
            for section, keys in settings.items() for key in keys)))
    assert len(shapes) == 1
    assert len(next(iter(shapes))) == 11


def test_the_processor_is_the_same_in_all_of_them():
    """NeXT's line was on the 68040 by the time of these machines, and Previous
    models nothing earlier that boots this disk."""
    for machine in machines.CATALOGUE:
        assert machines.settings_for(machine)["System"]["nCpuLevel"] == "4"


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
            assert machine.kind == 2, machine.identifier


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


def test_every_value_written_is_a_string():
    """A configuration file holds text. An integer here would become one in the
    file through whatever formatting happened to be in the way."""
    for machine in machines.CATALOGUE:
        for keys in machines.settings_for(machine).values():
            assert all(isinstance(value, str) for value in keys.values())
