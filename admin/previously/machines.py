"""Which machines can be configured, and what each one is in the file.

A machine is not one setting. Choosing a NeXTcube Turbo means a machine type, a
processor level, a clock, whether the colour board is seated, which slot it
speaks from, and four memory banks, and getting one of them wrong produces a
machine that either will not boot or is not the machine that was asked for.
Previous's own dialogue moves them together when the type changes there, and
this does the same.

The rules come from Previous itself, out of `Configuration_SetSystemDefaults`
and `Configuration_CheckMemory` in its `src/configuration.c`. That function is
what the emulator's own dialogue runs when somebody changes the machine there,
and it decides seven settings from the type, the turbo board and the colour
board together. Writing some of them and leaving the others produces a machine
Previous cannot run: it resets in a loop and shows a white screen, with nothing
in the log to say why.

Everything else in previous.cfg belongs to the installation rather than to the
machine and is left exactly as it stands.
"""

import collections

#: The processor. NeXT's 1988 machine is a 68030 and everything after it a
#: 68040, and Previous refuses to run a machine whose level disagrees with its
#: type.
CPU_LEVEL_68030 = "3"
CPU_LEVEL_68040 = "4"

#: The floating point unit that goes with each. A 68040 carries one on the
#: chip, which is what Previous means by the 68040 written here.
FPU_68882 = "68882"
FPU_ON_CHIP = "68040"

#: The clock in megahertz. A turbo board is the faster machine, and Nitro was a
#: faster turbo rather than a different one.
PLAIN_MHZ = "25"
TURBO_MHZ = "33"
NITRO_MHZ = "40"

#: Which slot a NeXTdimension board answers from. Zero means no board.
DIMENSION_SLOT = "2"
NO_BOARD = "0"

#: The 1988 machine, the cube and the station, as Previous numbers them in
#: nMachineType. Everything below is decided by which of the three it is.
NEXT_COMPUTER = 0
NEXTCUBE = 1
NEXTSTATION = 2

#: Which sizes one memory bank accepts, in megabytes, by what the machine is.
#: From Configuration_CheckMemory in Previous's src/configuration.c, which asks
#: in this order: a turbo board decides first, then colour, then what is left.
#: Anything in between is rounded up to the next of these and anything above
#: the largest is capped at it.
TURBO_BANK_SIZES = (0, 2, 8, 32)
COLOUR_BANK_SIZES = (0, 2, 8)
PLAIN_BANK_SIZES = (0, 1, 4, 16)

#: How many banks the machine holds, and how many of them a NeXTstation without
#: a turbo board and without colour can reach. On that board the other two are
#: not physically there, and Previous empties them at every start rather than
#: when the machine is chosen, so a file that fills them is corrected under
#: whoever wrote it.
BANKS = 4
STATION_PLAIN_BANKS = 2

Machine = collections.namedtuple(
    "Machine", "identifier name kind turbo nitro colour dimension banks")

#: Every machine that can be chosen, in the order they were built.
#:
#: `banks` is the four memory banks in megabytes. These are data rather than a
#: rule: a turbo takes 32 MB modules and an early station was sold with two
#: banks filled, and no arithmetic connects those facts.
CATALOGUE = (
    Machine("next-computer", "NeXT Computer", NEXT_COMPUTER,
            turbo=False, nitro=False, colour=False, dimension=False,
            banks=(16, 16, 16, 16)),
    Machine("nextcube", "NeXTcube", NEXTCUBE,
            turbo=False, nitro=False, colour=False, dimension=False,
            banks=(16, 16, 16, 16)),
    Machine("nextcube-dimension", "NeXTcube mit NeXTdimension", NEXTCUBE,
            turbo=False, nitro=False, colour=False, dimension=True,
            banks=(16, 16, 16, 16)),
    Machine("nextcube-turbo", "NeXTcube Turbo", NEXTCUBE,
            turbo=True, nitro=False, colour=False, dimension=False,
            banks=(32, 32, 32, 32)),
    Machine("nextcube-turbo-dimension", "NeXTcube Turbo mit NeXTdimension", NEXTCUBE,
            turbo=True, nitro=False, colour=False, dimension=True,
            banks=(32, 32, 32, 32)),
    Machine("nextcube-turbo-nitro", "NeXTcube Turbo Nitro", NEXTCUBE,
            turbo=True, nitro=True, colour=False, dimension=False,
            banks=(32, 32, 32, 32)),
    Machine("nextstation", "NeXTstation", NEXTSTATION,
            turbo=False, nitro=False, colour=False, dimension=False,
            banks=(16, 16, 0, 0)),
    Machine("nextstation-color", "NeXTstation Color", NEXTSTATION,
            turbo=False, nitro=False, colour=True, dimension=False,
            banks=(8, 8, 8, 8)),
    Machine("nextstation-turbo", "NeXTstation Turbo", NEXTSTATION,
            turbo=True, nitro=False, colour=False, dimension=False,
            banks=(32, 32, 32, 32)),
    Machine("nextstation-turbo-color", "NeXTstation Turbo Color", NEXTSTATION,
            turbo=True, nitro=False, colour=True, dimension=False,
            banks=(32, 32, 32, 32)),
    Machine("nextstation-turbo-color-nitro", "NeXTstation Turbo Color Nitro", NEXTSTATION,
            turbo=True, nitro=True, colour=True, dimension=False,
            banks=(32, 32, 32, 32)),
)

#: By identifier, which is what a request carries.
BY_IDENTIFIER = {machine.identifier: machine for machine in CATALOGUE}


def find(identifier):
    """The machine of that name.

    @param identifier - What a request asked for.
    @returns Machine, or None where nothing is called that. Unknown is not an
      error here: the caller decides what to say about it.
    """
    return BY_IDENTIFIER.get(identifier)


def settings_for(machine):
    """What this machine is, expressed as the file's own keys.

    @param machine - A Machine.
    @returns dict of section name to dict of key to value, all strings,
      because that is what a configuration file holds.

    Only the keys that differ between machines appear. Everything else in
    previous.cfg belongs to the installation rather than to the machine and is
    none of this function's business.
    """
    return {
        "System": _system_for(machine),
        "Dimension": {
            "bEnabled0": _flag(machine.dimension),
            # The board answers from slot 2, and a machine without one says
            # zero rather than leaving the key at whatever it was.
            "nConsoleSlot": DIMENSION_SLOT if machine.dimension else NO_BOARD,
        },
        "Memory": {
            "nMemoryBankSize%d" % index: str(size)
            for index, size in enumerate(machine.banks)
        },
    }


def whole(value, fallback):
    """One number, however it arrived.

    @param value - What was given, which from a browser is text and from a file
      somebody edited may be anything at all.
    @param fallback - What to answer where it is not a number.
    @returns int

    Here rather than in each module that needs it, because `saved.py` asks the
    same question of a file that this asks of a query string, and two answers to
    it would part company the first time one of them learned something.
    """
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def bank_sizes(kind, turbo, colour):
    """Which sizes each of the four memory banks accepts.

    @param kind - NEXT_COMPUTER, NEXTCUBE or NEXTSTATION.
    @param turbo - Whether a turbo board is seated, as settled() leaves it.
    @param colour - Whether the colour board is, the same way.
    @returns tuple of four tuples of megabytes, one per bank in the order they
      sit in. A bank the machine cannot reach offers nothing but zero, which is
      a choice of one rather than an absence, so whatever draws this has four
      banks to draw either way.

    Taking the two flags rather than a Machine, because they have to be the
    settled ones: a cube with colour asked for is a cube without it, and
    reading a bank rule off a choice the emulator refuses would offer sizes no
    machine has.
    """
    if turbo:
        sizes = TURBO_BANK_SIZES
    elif colour:
        sizes = COLOUR_BANK_SIZES
    else:
        sizes = PLAIN_BANK_SIZES

    reachable = BANKS
    if kind == NEXTSTATION and not turbo and not colour:
        reachable = STATION_PLAIN_BANKS
    return tuple(sizes if bank < reachable else (0,) for bank in range(BANKS))


#: What a total of memory is made of, bank by bank, in megabytes. From
#: `defmemsize` in Previous's src/gui-sdl/dlgAdvanced.c, which is the table its
#: own dialogue fills the four banks from when somebody picks a size there.
#:
#: Two families, because the same total is laid out differently: a plain
#: monochrome machine takes 16 MB modules and anything with a turbo board or a
#: colour board takes 8 and 32 MB ones.
PLAIN_MEMORY = {
    8: (4, 4, 0, 0),
    16: (16, 0, 0, 0),
    32: (16, 16, 0, 0),
    64: (16, 16, 16, 16),
}
WIDE_MEMORY = {
    8: (8, 0, 0, 0),
    16: (8, 8, 0, 0),
    32: (8, 8, 8, 8),
    64: (32, 32, 0, 0),
    128: (32, 32, 32, 32),
}

#: Which of those totals each kind of machine is offered, from the same
#: dialogue, which takes the larger two away where the board cannot hold them:
#: 128 MB wants a turbo board, and 64 MB wants either that or the four banks a
#: monochrome cube has.
TURBO_MEMORY = (8, 16, 32, 64, 128)
CUBE_MEMORY = (8, 16, 32, 64)
NARROW_MEMORY = (8, 16, 32)


def memory_totals(kind, turbo, colour):
    """How much memory this machine can be given, in megabytes.

    @param kind - NEXT_COMPUTER, NEXTCUBE or NEXTSTATION.
    @param turbo - Whether a turbo board is seated, as settled() leaves it.
    @param colour - Whether the colour board is, the same way.
    @returns tuple of int, smallest first.

    A total rather than four banks, because that is what Previous's own dialogue
    offers and what a person means by how much memory a machine has. Which
    modules make it up follows from the machine, and PLAIN_MEMORY and
    WIDE_MEMORY are that.
    """
    if turbo:
        return TURBO_MEMORY
    if colour or kind == NEXTSTATION:
        # A colour board takes 8 MB modules and fills all four banks at 32, and
        # a plain station reaches only two banks at all. Both stop at 32.
        return NARROW_MEMORY
    return CUBE_MEMORY


def banks_for(total, kind, turbo, colour):
    """The four banks a total of memory is made up of.

    @param total - How much memory, in megabytes.
    @param kind - The machine type.
    @param turbo - Whether a turbo board is seated, as settled() leaves it.
    @param colour - Whether the colour board is, the same way.
    @returns tuple of four ints.

    A total the machine is not offered is answered with the largest it is
    offered that is no bigger, and with the smallest where even that is too
    small. Somebody moving from a turbo machine to a plain one has asked for
    128 MB of a board that holds 64, and the honest answer to that is the
    machine they can have rather than a refusal.
    """
    offered = memory_totals(kind, turbo, colour)
    layouts = WIDE_MEMORY if (turbo or colour) else PLAIN_MEMORY
    wanted = whole(total, offered[0])
    fits = [size for size in offered if size <= wanted] or [offered[0]]
    return layouts[fits[-1]]


def drafted(kind, turbo=False, colour=False, dimension=False,
            mhz=None, memory=None, identifier="", name=""):
    """A machine from what an editor is showing, held to Previous's rules.

    @param kind - The machine type, as a number or a string of one.
    @param turbo - Whether a turbo board is asked for.
    @param colour - Whether the colour board is.
    @param dimension - Whether a NeXTdimension is.
    @param mhz - The clock asked for. Only a turbo machine has a choice, and
      there it is the 33 of a Turbo against the 40 somebody types for a Nitro.
    @param memory - How much memory, as a total in megabytes.
    @param identifier - What it is called to the API, where it has a name.
    @param name - What it is called to a person.
    @returns Machine, settled.

    The six values this takes are the six controls an editor draws, one each,
    and nothing about them is a rule: which of them may be chosen at all is
    offers(), and what they turn into is here and in settled(). So an interface
    holds no copy of anything Previous decides.

    Nitro is not one of the six. Previous has no such thing and reads nCpuFreq
    as it finds it, so a clock of 40 is what the catalogue calls a Nitro and
    that is the direction the translation runs in.
    """
    machine = settled(Machine(
        identifier=identifier,
        name=name,
        kind=whole(kind, NEXTCUBE),
        turbo=bool(turbo),
        nitro=str(mhz) == NITRO_MHZ,
        colour=bool(colour),
        dimension=bool(dimension),
        banks=(0, 0, 0, 0),
    ))
    # After the flags, because they decide which totals there are and what each
    # one is made of.
    return machine._replace(
        banks=banks_for(memory, machine.kind, machine.turbo, machine.colour))


def offers(machine):
    """What may be chosen for a machine like this one.

    @param machine - A Machine, settled.
    @returns dict, one entry per control an editor draws: the machine types,
      whether the turbo board, the colour board and a NeXTdimension may be
      seated at all, which clocks there are, and which totals of memory.

    Answered by the service rather than worked out in the browser, so there is
    one statement of what Previous allows and an interface cannot offer a
    machine the emulator would correct underneath it.

    The clocks are numbers here and strings in the file, because a browser
    compares them against what somebody chose and the file holds text.
    """
    return {
        "kinds": [NEXT_COMPUTER, NEXTCUBE, NEXTSTATION],
        "turbo": machine.kind != NEXT_COMPUTER,
        "colour": machine.kind == NEXTSTATION,
        "dimension": machine.kind != NEXTSTATION,
        "clocks": [int(TURBO_MHZ), int(NITRO_MHZ)] if machine.turbo else [],
        "memory": list(memory_totals(
            machine.kind, machine.turbo, machine.colour)),
    }


def settled(machine):
    """The machine Previous would run, given what somebody put together.

    @param machine - A Machine, which may hold a choice the emulator does not
      allow: colour on a cube, a board in a station, memory in a bank that is
      not there.
    @returns Machine, identical in everything Previous accepts and corrected in
      everything it does not.

    Previous never refuses a configuration. It corrects one, in two places, and
    both are in its src/configuration.c. Its own dialogue runs
    Configuration_SetSystemDefaults whenever the machine type changes there, and
    Configuration_Apply runs the four check functions at every start, whatever
    wrote the file. So a configuration that has not been through this is one the
    emulator will quietly change underneath whoever saved it, and the interface
    would then be showing a machine that is not the one running.

    This is why it is applied when a saved configuration is read as well as when
    it is written: a file somebody edited by hand gets the same treatment as one
    this tool wrote.
    """
    turbo = machine.turbo and machine.kind != NEXT_COMPUTER
    colour = machine.colour and machine.kind == NEXTSTATION
    # A bank that was left out is an empty one, and a fifth is not a bank. Both
    # are what a hand-written file can hold.
    wanted = tuple(machine.banks) + (0,) * BANKS
    sizes = bank_sizes(machine.kind, turbo, colour)

    return machine._replace(
        turbo=turbo,
        # A Nitro is a faster turbo board rather than a machine of its own, so
        # without that board there is nothing for it to be faster than. This one
        # rule is ours: Previous has no idea of Nitro and reads nCpuFreq as it
        # finds it.
        nitro=machine.nitro and turbo,
        colour=colour,
        # The board speaks on the NeXTbus and a NeXTstation has none, so
        # Configuration_CheckDimensionSettings switches every board off for that
        # machine type. Both cubes have the bus and therefore the slot.
        dimension=machine.dimension and machine.kind != NEXTSTATION,
        banks=tuple(_bank(wanted[bank], sizes[bank]) for bank in range(BANKS)),
    )


def _system_for(machine):
    """The System section, which is where a machine is really decided.

    @param machine - A Machine.
    @returns dict of key to value, all strings.

    Every value here follows from the type, the turbo board and the colour
    board, exactly as Previous's own Configuration_SetSystemDefaults derives
    them. They are written together because they only make sense together: a
    machine with one chip of a turbo and one of a plain board is not a machine,
    and Previous answers it by resetting for ever.
    """
    is_1988 = machine.kind == NEXT_COMPUTER
    return {
        "nMachineType": str(machine.kind),
        "nCpuLevel": CPU_LEVEL_68030 if is_1988 else CPU_LEVEL_68040,
        "nCpuFreq": _clock(machine),
        "n_FPUType": FPU_68882 if is_1988 else FPU_ON_CHIP,
        "bTurbo": _flag(machine.turbo),
        "bColor": _flag(machine.colour),
        # The real-time clock. A turbo board carries the MCCS1850, and so does
        # a colour station, whilst everything else has the MC68HC68T1. Previous
        # writes the choice as a boolean, and TRUE is the MCCS1850.
        "nRTC": _flag(machine.turbo or (machine.kind == NEXTSTATION and machine.colour)),
        # The SCSI controller, as a boolean the same way: the 1988 machine has
        # the NCR53C90 and every 68040 the NCR53C90A.
        "nSCSI": _flag(not is_1988),
        # The NeXTbus interface chip sits in the cubes, which have a bus, and
        # not in the station, which has none.
        "bNBIC": _flag(machine.kind != NEXTSTATION),
        # The 1988 machine's DSP has no expansion memory and every later one
        # has.
        "bDSPMemoryExpansion": _flag(not is_1988),
    }


def _clock(machine):
    """@returns The clock in megahertz, as the file holds it."""
    if machine.nitro:
        return NITRO_MHZ
    return TURBO_MHZ if machine.turbo else PLAIN_MHZ


def _bank(size, sizes):
    """One memory bank, held to a size the machine accepts.

    @param size - What was asked for, in megabytes.
    @param sizes - What that bank offers, as bank_sizes answers.
    @returns int

    Rounded up to the next size offered and capped at the largest, which is what
    Configuration_CheckMemory does: three megabytes on a turbo board is a bank of
    eight, and sixty-four is a bank of thirty-two. Anything that is not a number
    at all, which a hand-edited file can hold, is an empty bank.
    """
    try:
        wanted = int(size)
    except (TypeError, ValueError):
        return 0
    if wanted <= 0:
        return 0
    for offered in sizes:
        if wanted <= offered:
            return offered
    return sizes[-1]


def _flag(value):
    """@returns The word Previous writes for a boolean."""
    return "TRUE" if value else "FALSE"
