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


# -- a machine somebody put together -------------------------------------


def drafted(**wanted):
    """A machine as the Config Editor hands one over, before any rule is kept.

    @param wanted - Whatever this test is about. Everything else is a plain
      NeXTcube with no memory, so a test says only what it means.
    @returns machines.Machine
    """
    fields = {
        "identifier": "user:Drafted",
        "name": "Drafted",
        "kind": machines.NEXTCUBE,
        "turbo": False,
        "nitro": False,
        "colour": False,
        "dimension": False,
        "banks": (16, 16, 16, 16),
    }
    fields.update(wanted)
    return machines.Machine(**fields)


def test_the_eleven_are_already_what_previous_would_make_of_them():
    """The one test that would have caught #66. A shipped machine holding a
    choice the emulator corrects at every start is a machine whose name in the
    interface is not the machine that runs."""
    for machine in machines.CATALOGUE:
        assert machines.settled(machine) == machine, machine.identifier


def test_settling_a_settled_machine_changes_nothing():
    """It is applied when a configuration is written and again when it is read,
    so the second pass has to leave the first alone."""
    once = machines.settled(drafted(kind=machines.NEXTSTATION, colour=True,
                                    dimension=True, banks=(3, 0, 9, 40)))
    assert machines.settled(once) == once


def test_a_cube_cannot_have_colour():
    """Previous forces bColor off for both cube types, so a cube saved with it
    would come back without it and the interface would have said colour."""
    for kind in [machines.NEXT_COMPUTER, machines.NEXTCUBE]:
        assert machines.settled(drafted(kind=kind, colour=True)).colour is False


def test_only_a_station_keeps_colour():
    assert machines.settled(
        drafted(kind=machines.NEXTSTATION, colour=True)).colour is True


def test_the_1988_machine_cannot_have_a_turbo_board():
    """NeXT built none, and Previous forces the flag off for that type."""
    computer = machines.settled(drafted(kind=machines.NEXT_COMPUTER, turbo=True))
    assert computer.turbo is False


def test_a_station_cannot_hold_a_dimension():
    """The board speaks on the NeXTbus and a station has none, so Previous
    switches it off at every start whatever the file says."""
    station = machines.settled(drafted(kind=machines.NEXTSTATION, dimension=True))
    assert station.dimension is False


def test_both_cubes_take_a_dimension():
    """Previous refuses the board for the station alone, so the 1988 machine has
    the slot as much as the 040 cube does."""
    for kind in [machines.NEXT_COMPUTER, machines.NEXTCUBE]:
        assert machines.settled(drafted(kind=kind, dimension=True)).dimension is True


def test_nitro_without_a_turbo_board_is_not_nitro():
    """A Nitro is a faster turbo board rather than a machine of its own."""
    assert machines.settled(drafted(nitro=True, turbo=False)).nitro is False
    assert machines.settled(drafted(nitro=True, turbo=True)).nitro is True


def test_a_bank_is_rounded_up_to_a_size_the_machine_has():
    """Previous rounds every bank up to the next size it accepts and caps it at
    the largest, so a number in between is a bank of the size above it."""
    turbo = machines.settled(drafted(turbo=True, banks=(1, 3, 9, 64)))
    assert turbo.banks == (2, 8, 32, 32)

    plain = machines.settled(drafted(banks=(1, 2, 5, 64)))
    assert plain.banks == (1, 4, 16, 16)

    colour = machines.settled(
        drafted(kind=machines.NEXTSTATION, colour=True, banks=(1, 3, 9, 64)))
    assert colour.banks == (2, 8, 8, 8)


def test_an_empty_bank_stays_empty():
    """A socket with nothing in it is not rounded up to the smallest module."""
    assert machines.settled(drafted(banks=(16, 0, 0, 0))).banks == (16, 0, 0, 0)


def test_a_plain_station_reaches_two_banks_only():
    """On that board the other two are not physically there, and Previous
    empties them at every start rather than when the machine is chosen."""
    station = machines.settled(
        drafted(kind=machines.NEXTSTATION, banks=(16, 16, 16, 16)))
    assert station.banks == (16, 16, 0, 0)


def test_colour_and_turbo_give_a_station_all_four_banks():
    """The restriction is on the plain monochrome board alone."""
    colour = machines.settled(
        drafted(kind=machines.NEXTSTATION, colour=True, banks=(8, 8, 8, 8)))
    turbo = machines.settled(
        drafted(kind=machines.NEXTSTATION, turbo=True, banks=(32, 32, 32, 32)))

    assert colour.banks == (8, 8, 8, 8)
    assert turbo.banks == (32, 32, 32, 32)


def test_a_bank_that_is_not_a_number_is_an_empty_one():
    """A configuration file can be edited by hand, and what comes back from one
    is whatever somebody typed."""
    assert machines.settled(drafted(banks=("", None, "sixteen", 16))).banks == \
        (0, 0, 0, 16)


def test_a_configuration_with_the_wrong_number_of_banks_gets_four():
    """A machine holds four, so a shorter list is banks nobody filled and a
    longer one is a bank that is not there."""
    assert machines.settled(drafted(banks=(16,))).banks == (16, 0, 0, 0)
    assert machines.settled(drafted(banks=(16, 16, 16, 16, 16))).banks == \
        (16, 16, 16, 16)


def test_an_unreachable_bank_offers_nothing_but_zero():
    """So whatever draws this has four banks to draw either way, and the two a
    plain station cannot reach are a choice of one rather than an absence."""
    offered = machines.bank_sizes(machines.NEXTSTATION, turbo=False, colour=False)

    assert offered[0] == machines.PLAIN_BANK_SIZES
    assert offered[2] == (0,)
    assert len(offered) == machines.BANKS


def test_what_each_kind_of_machine_offers_a_bank():
    assert machines.bank_sizes(machines.NEXTCUBE, turbo=True, colour=False)[0] == \
        machines.TURBO_BANK_SIZES
    assert machines.bank_sizes(machines.NEXTSTATION, turbo=False, colour=True)[0] == \
        machines.COLOUR_BANK_SIZES
    assert machines.bank_sizes(machines.NEXTCUBE, turbo=False, colour=False)[0] == \
        machines.PLAIN_BANK_SIZES


def test_a_turbo_board_decides_the_sizes_before_colour_does():
    """Previous asks in that order, so a colour turbo station takes the turbo
    sizes rather than the colour ones."""
    assert machines.bank_sizes(machines.NEXTSTATION, turbo=True, colour=True)[0] == \
        machines.TURBO_BANK_SIZES
