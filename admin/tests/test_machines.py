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
    assert len(next(iter(shapes))) == 18


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
        if machine.mhz == machines.NITRO_MHZ:
            assert machine.turbo is True, machine.identifier
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
        assert sorted(memory) == (
            ["nMemoryBankSize%d" % i for i in range(4)] + ["nMemorySpeed"])
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
        "mhz": machines.PLAIN_MHZ,
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
    """A Nitro is a faster turbo board rather than a machine of its own, so the
    clock it runs at is offered nowhere without that board."""
    assert machines.settled(drafted(mhz=40, turbo=False)).mhz == 25
    assert machines.settled(drafted(mhz=40, turbo=True)).mhz == 40


def test_a_clock_the_machine_cannot_have_becomes_the_one_its_boards_give_it():
    """Previous writes the clock afresh whenever the machine type or the turbo
    board changes in its own dialogue, so a machine holding one it is not
    offered gets the one that goes with what it is now."""
    assert machines.settled(drafted(turbo=True, mhz=0)).mhz == 33
    assert machines.settled(drafted(turbo=False, mhz=0)).mhz == 25
    assert machines.settled(drafted(turbo=False, mhz=99)).mhz == 25


def test_every_machine_keeps_a_clock_previous_offers_it():
    """The four slow ones are offered whatever the machine is, so choosing one
    of them survives a change of board."""
    for clock in (16, 20, 25, 33):
        assert machines.settled(drafted(turbo=False, mhz=clock)).mhz == clock
        assert machines.settled(drafted(turbo=True, mhz=clock)).mhz == clock


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


# -- how much memory, as a total ------------------------------------------


def test_every_shipped_machine_holds_a_total_that_can_be_chosen():
    """The editor offers memory as a total, so opening one of the eleven has to
    land on one of those rather than on nothing. All eleven do, and their banks
    are exactly the layout that total is made of."""
    for machine in machines.CATALOGUE:
        total = sum(machine.banks)
        offered = machines.memory_totals(
            machine.kind, machine.turbo, machine.colour)

        assert total in offered, (machine.identifier, total, offered)
        assert machines.banks_for(
            total, machine.kind, machine.turbo, machine.colour) == machine.banks, \
            machine.identifier


def test_which_totals_each_machine_is_offered():
    """From Previous's own dialogue, which takes the larger two away where the
    board cannot hold them."""
    assert machines.memory_totals(machines.NEXTCUBE, turbo=True, colour=False) == \
        (8, 16, 32, 64, 128)
    # A monochrome cube has four banks of 16 and stops at 64.
    assert machines.memory_totals(machines.NEXTCUBE, turbo=False, colour=False) == \
        (8, 16, 32, 64)
    # A colour board fills all four banks at 32, and a plain station reaches
    # only two banks at all. Both stop there.
    assert machines.memory_totals(machines.NEXTSTATION, turbo=False, colour=True) == \
        (8, 16, 32)
    assert machines.memory_totals(machines.NEXTSTATION, turbo=False, colour=False) == \
        (8, 16, 32)


def test_a_total_is_made_of_the_modules_that_machine_takes():
    """The same total is laid out differently: 16 MB is one module on a plain
    machine and two on anything with a turbo or a colour board."""
    plain = machines.banks_for(16, machines.NEXTCUBE, turbo=False, colour=False)
    turbo = machines.banks_for(16, machines.NEXTCUBE, turbo=True, colour=False)

    assert plain == (16, 0, 0, 0)
    assert turbo == (8, 8, 0, 0)
    assert sum(plain) == sum(turbo) == 16


def test_a_total_the_machine_cannot_hold_becomes_the_largest_it_can():
    """Somebody moving from a turbo machine to a plain station has asked for
    128 MB of a board that holds 32, and the machine they can have is a better
    answer than a refusal."""
    banks = machines.banks_for(128, machines.NEXTSTATION, turbo=False, colour=False)

    assert banks == (16, 16, 0, 0)
    assert sum(banks) == 32


def test_a_total_below_the_smallest_becomes_the_smallest():
    assert sum(machines.banks_for(1, machines.NEXTCUBE, turbo=True, colour=False)) == 8
    assert sum(machines.banks_for(
        "not a number", machines.NEXTCUBE, turbo=True, colour=False)) == 8


# -- a machine as an editor holds one ------------------------------------


def test_a_draft_is_the_six_controls_and_nothing_else():
    """What an editor draws is six choices, and everything that follows from
    them follows here rather than in the browser."""
    machine = machines.drafted(kind=machines.NEXTSTATION, turbo=True, colour=True,
                               mhz=40, memory=128, name="Meine Kiste")

    assert machine.name == "Meine Kiste"
    assert machine.turbo is True
    assert machine.colour is True
    assert machine.mhz == 40
    assert machine.banks == (32, 32, 32, 32)
    assert machines.settings_for(machine)["System"]["nCpuFreq"] == "40"


def test_a_draft_arrives_as_text_and_is_read_as_numbers():
    """It comes off a query string, so every value in it is a string."""
    machine = machines.drafted(kind="2", turbo=True, colour=True,
                               mhz="40", memory="32")

    assert machine.kind == machines.NEXTSTATION
    assert machine.mhz == 40
    assert sum(machine.banks) == 32


def test_a_draft_that_names_no_clock_gets_the_one_its_boards_give_it():
    """Which is what an editor sends the moment the machine type or a board
    changes, because Previous sets the clock afresh at both of those."""
    assert machines.drafted(kind=machines.NEXTCUBE, turbo=True, memory=32).mhz == 33
    assert machines.drafted(kind=machines.NEXTCUBE, turbo=False, memory=32).mhz == 25


def test_a_draft_that_asks_for_what_previous_refuses_comes_back_without_it():
    cube = machines.drafted(kind=machines.NEXTCUBE, colour=True, memory=16)
    station = machines.drafted(kind=machines.NEXTSTATION, dimension=True, memory=16)
    computer = machines.drafted(kind=machines.NEXT_COMPUTER, turbo=True, memory=16)

    assert cube.colour is False
    assert station.dimension is False
    assert computer.turbo is False


def test_the_faster_clock_needs_the_board_it_belongs_to():
    """A Nitro is a faster turbo board. Previous has no idea of it and reads the
    clock as it finds it, so 40 without a turbo is not a machine."""
    without = machines.drafted(kind=machines.NEXTCUBE, turbo=False, mhz=40, memory=16)

    assert without.mhz == 25
    assert machines.settings_for(without)["System"]["nCpuFreq"] == "25"


def test_the_memory_follows_the_machine_the_draft_turned_out_to_be():
    """The flags are settled first, because they decide which totals there are
    and what each one is made of. A cube asked for in colour is a cube."""
    cube = machines.drafted(kind=machines.NEXTCUBE, colour=True, memory=64)

    assert cube.colour is False
    # The monochrome layout for 64, rather than the colour board's, which has no
    # 64 at all.
    assert cube.banks == (16, 16, 16, 16)


# -- what an editor may offer --------------------------------------------


def test_the_1988_machine_offers_no_turbo_board():
    assert machines.offers(machines.find("next-computer"))["turbo"] is False
    assert machines.offers(machines.find("nextcube"))["turbo"] is True


def test_only_a_station_offers_colour_and_only_a_cube_a_dimension():
    station = machines.offers(machines.find("nextstation"))
    cube = machines.offers(machines.find("nextcube"))

    assert station["colour"] is True
    assert station["dimension"] is False
    assert cube["colour"] is False
    assert cube["dimension"] is True


def test_a_clock_is_offered_only_where_there_is_a_turbo_board():
    """The four slow ones are offered whatever the machine is, and the fastest
    only where the board that carries it is seated, which is what Previous does
    by replacing that option with blank space."""
    assert machines.offers(machines.find("nextcube"))["clocks"] == [16, 20, 25, 33]
    assert machines.offers(machines.find("next-computer"))["clocks"] == [16, 20, 25, 33]
    assert machines.offers(machines.find("nextcube-turbo"))["clocks"] == [16, 20, 25, 33, 40]


def test_every_machine_is_offered_all_three_dsps():
    """Neither of the two that are a chip loads a file, so there is nothing a
    machine can lack that would stop it being offered."""
    for machine in machines.CATALOGUE:
        assert machines.offers(machine)["dsps"] == [
            "none", "plain", "with-rom"], machine.identifier


def test_the_dsp_memory_is_offered_only_where_there_is_a_chip():
    assert machines.offers(drafted(dsp="none"))["dsp_memory"] == []
    assert machines.offers(drafted(dsp="plain"))["dsp_memory"] == [24, 96]


def test_what_previous_is_told_about_the_dsp():
    """Its own enumeration reads none, accurate, emulated, so the number for the
    chip with its bootstrap ROM is the middle one rather than the last."""
    written = {}
    for dsp in machines.DSPS:
        written[dsp] = machines.settings_for(
            drafted(dsp=dsp))["System"]["nDSPType"]

    assert written == {"none": "0", "with-rom": "1", "plain": "2"}


def test_the_dsp_memory_is_written_as_the_flag_previous_holds():
    assert machines.settings_for(
        drafted(dsp_memory=96))["System"]["bDSPMemoryExpansion"] == "TRUE"
    assert machines.settings_for(
        drafted(dsp_memory=24))["System"]["bDSPMemoryExpansion"] == "FALSE"


def test_a_dsp_the_machine_cannot_have_becomes_the_one_it_has():
    """Previous writes both afresh whenever the machine type or a board changes,
    and never checks either at start."""
    assert machines.settled(drafted(dsp="grosser Chip")).dsp == "plain"
    assert machines.settled(drafted(dsp_memory=48)).dsp_memory == 96
    assert machines.settled(
        drafted(kind=machines.NEXT_COMPUTER, dsp_memory=48)).dsp_memory == 24


def test_only_the_1988_machine_has_a_dsp_without_the_expansion():
    for machine in machines.CATALOGUE:
        wanted = 24 if machine.kind == machines.NEXT_COMPUTER else 96
        assert machine.dsp_memory == wanted, machine.identifier
        assert machine.dsp == "plain", machine.identifier


def test_a_turbo_board_reads_the_same_memory_speeds_differently():
    """The file holds a position rather than a time, and Previous relabels the
    four for a turbo board, so the same machine setting means faster memory
    there."""
    plain = machines.offers(machines.find("nextcube"))["memory_speeds"]
    turbo = machines.offers(machines.find("nextcube-turbo"))["memory_speeds"]

    assert [offer["ns"] for offer in plain] == [120, 100, 80, 60]
    assert [offer["ns"] for offer in turbo] == [60, 70, 80, 100]
    assert [offer["speed"] for offer in plain] == [0, 1, 2, 3]


def test_the_memory_speed_is_written_as_the_position_previous_holds():
    assert machines.settings_for(
        drafted(memory_speed=3))["Memory"]["nMemorySpeed"] == "3"


def test_a_memory_speed_that_is_not_a_position_becomes_the_one_previous_starts_from():
    assert machines.settled(drafted(memory_speed=9)).memory_speed == 1
    assert machines.settled(drafted(memory_speed=-1)).memory_speed == 1
    assert machines.settled(drafted(memory_speed=0)).memory_speed == 0


def test_the_memory_speed_survives_a_change_of_machine():
    """Previous leaves it alone when the machine type or a board changes, unlike
    the clock and the DSP, so a position somebody chose is still theirs."""
    assert machines.drafted(kind=machines.NEXTSTATION, turbo=True,
                            memory_speed=3, memory=32).memory_speed == 3


def test_every_machine_starts_where_previous_starts():
    for machine in machines.CATALOGUE:
        assert machine.memory_speed == 1, machine.identifier


def test_a_bank_can_be_chosen_on_its_own():
    """Which is the whole point of it: a machine no total adds up to."""
    machine = machines.drafted(kind=machines.NEXTCUBE, turbo=False,
                               banks=(16, 4, 0, 0))

    assert machine.banks == (16, 4, 0, 0)
    assert sum(machine.banks) == 20


def test_banks_arrive_as_text_and_are_read_as_numbers():
    """They come off a query string, one field holding all four."""
    machine = machines.drafted(kind=machines.NEXTCUBE, banks="16,16,0,0")

    assert machine.banks == (16, 16, 0, 0)


def test_a_bank_chosen_on_its_own_is_still_held_to_what_the_machine_takes():
    """Three megabytes is not a module a plain machine has, and a station
    without a turbo board or colour cannot reach the last two banks at all."""
    assert machines.drafted(kind=machines.NEXTCUBE, banks=(3, 0, 0, 0)
                            ).banks == (4, 0, 0, 0)
    assert machines.drafted(kind=machines.NEXTSTATION, banks=(16, 16, 16, 16)
                            ).banks == (16, 16, 0, 0)


def test_naming_the_banks_wins_over_the_total():
    """An editor sends one or the other, and the banks are the finer of the two,
    so a total sent beside them would undo what was just chosen."""
    machine = machines.drafted(kind=machines.NEXTCUBE, banks=(4, 0, 0, 0),
                               memory=64)

    assert machine.banks == (4, 0, 0, 0)


def test_no_bank_named_leaves_the_total_in_charge():
    assert machines.drafted(kind=machines.NEXTCUBE, memory=64
                            ).banks == (16, 16, 16, 16)
    assert machines.drafted(kind=machines.NEXTCUBE, memory=64, banks=""
                            ).banks == (16, 16, 16, 16)


def test_what_each_bank_takes_is_offered():
    """Four of them always, because a bank the machine cannot reach offers an
    empty one rather than nothing, and an editor has four cells either way."""
    cube = machines.offers(machines.find("nextcube"))["banks"]
    station = machines.offers(machines.find("nextstation"))["banks"]

    assert cube == [[0, 1, 4, 16]] * 4
    assert station == [[0, 1, 4, 16], [0, 1, 4, 16], [0], [0]]


def test_every_machine_type_is_offered_always():
    """Choosing another one is how anything else changes, so it is the one
    control that never goes away. Each carries the name it is drawn with, which
    the browser has no other way of knowing."""
    for machine in machines.CATALOGUE:
        assert machines.offers(machine)["kinds"] == [
            {"kind": 0, "model": "NeXT Computer"},
            {"kind": 1, "model": "NeXTcube"},
            {"kind": 2, "model": "NeXTstation"},
        ], machine.identifier


def test_what_is_offered_is_what_the_machine_in_hand_holds():
    """An editor marks the chosen cell from the configuration and draws the cells
    from this, so a machine whose own value is not among them would show a row
    with nothing chosen in it."""
    for machine in machines.CATALOGUE:
        offered = machines.offers(machine)
        kinds = [offer["kind"] for offer in offered["kinds"]]
        assert machine.kind in kinds, machine.identifier
        assert sum(machine.banks) in offered["memory"], machine.identifier
        assert machine.mhz in offered["clocks"], machine.identifier
