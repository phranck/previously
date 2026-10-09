"""Which machines can be configured, and what each one is in the file.

A machine is not one setting. Choosing a NeXTcube Turbo means a machine type, a
processor level, a clock, whether the color board is seated, which slot it
speaks from, and four memory banks, and getting one of them wrong produces a
machine that either will not boot or is not the machine that was asked for.
Previous's own dialog moves them together when the type changes there, and
this does the same.

The rules come from Previous itself, out of `Configuration_SetSystemDefaults`
and `Configuration_CheckMemory` in its `src/configuration.c`. That function is
what the emulator's own dialog runs when somebody changes the machine there,
and it decides seven settings from the type, the turbo board and the color
board together. Writing some of them and leaving the others produces a machine
Previous cannot run: it resets in a loop and shows a white screen, with nothing
in the log to say why.

Everything else in previous.cfg belongs to the installation rather than to the
machine and is left exactly as it stands.
"""

import collections

from . import config

#: The processor. NeXT's 1988 machine is a 68030 and everything after it a
#: 68040, and Previous refuses to run a machine whose level disagrees with its
#: type.
CPU_LEVEL_68030 = "3"
CPU_LEVEL_68040 = "4"

#: The floating point unit that goes with each. A 68040 carries one on the
#: chip, which is what Previous means by the 68040 written here.
FPU_68882 = "68882"
FPU_ON_CHIP = "68040"

#: The clocks in megahertz, from the CPU clock group in Previous's
#: src/gui-sdl/dlgAdvanced.c. Its own dialog offers these four whatever the
#: machine is, and adds NITRO_MHZ only where a turbo board is seated.
CLOCKS = (16, 20, 25, 33)

#: The fifth, which is what the catalog calls a Nitro. Previous has no idea of
#: Nitro and reads nCpuFreq as it finds it, so this is a name of ours for the
#: fastest clock its own dialog will offer.
NITRO_MHZ = 40

#: What a machine runs at when nothing else has been chosen, which is what
#: Configuration_SetSystemDefaults writes every time the machine type or the
#: turbo board changes in Previous's own dialog.
PLAIN_MHZ = 25
TURBO_MHZ = 33

#: What the DSP can be. The chip is a 56001 either way and the difference is its
#: bootstrap ROM: DSP_WITH_ROM starts the core with it and DSP_PLAIN without,
#: which is what `dsp_core_start` in Previous's src/dsp/dsp.c takes as its
#: second argument. Neither is a file, so all three suit any machine.
DSP_NONE = "none"
DSP_PLAIN = "plain"
DSP_WITH_ROM = "with-rom"
DSPS = (DSP_NONE, DSP_PLAIN, DSP_WITH_ROM)

#: What Previous writes for each in nDSPType. Its own enumeration reads none,
#: accurate, emulated, so the numbers are not in the order a person would put
#: them in, and a name crosses the wire rather than a number for that reason.
DSP_TYPES = {DSP_NONE: "0", DSP_WITH_ROM: "1", DSP_PLAIN: "2"}

#: How much memory the DSP has, in kilobytes. Previous writes this as a flag,
#: and the expansion is what makes the difference between the two.
DSP_MEMORY_PLAIN = 24
DSP_MEMORY_EXPANDED = 96
DSP_MEMORIES = (DSP_MEMORY_PLAIN, DSP_MEMORY_EXPANDED)

#: What goes into nMemorySpeed, which is a position rather than a time. This is
#: where Previous starts every machine, from its own defaults in
#: src/configuration.c, and it never moves one: Configuration_SetSystemDefaults
#: does not touch the key.
#:
#: Not offered in the editor, because nothing in the emulator reads it except
#: the two functions that put it into System Control Register 1, which is what
#: the machine says about itself. It changes no timing, and two of the four
#: positions are not even distinct: src/sysReg.c maps both 100 and 120 ns to
#: MEM_120NS on a machine without a turbo board.
MEMORY_SPEED = 1

#: How many drives of each kind Previous keeps in its file. This tool offers a
#: machine one of each, because that is what NeXT built, and writes the rest as
#: absent so a configuration says plainly what the machine has.
FLOPPY_DRIVES = 4
OPTICAL_DRIVES = 2

#: Which of the two ethernet sockets NeXT built is in use. Thin wire is the
#: coaxial one every machine has, and twisted pair arrived with the 68040s.
THIN_WIRE = "thin-wire"
TWISTED_PAIR = "twisted-pair"
ETHERNET_SOCKETS = (THIN_WIRE, TWISTED_PAIR)

#: How many NeXTdimension boards a cube holds. Previous keeps three, and
#: ND_SLOT(n) in its src/dimension/dimension.hpp puts board n in slot n*2+2, so
#: they answer from slots 2, 4 and 6.
DIMENSION_BOARDS = 3

#: How much memory one of those boards can have, in megabytes. Its four banks
#: take 4 or 16 MB or nothing, so these are what a board evenly filled comes to.
#:
#: Zero means no board rather than a board with nothing in it, because there is
#: no such thing: Configuration_CheckDimensionMemory puts 4 MB in the first bank
#: of every board that is switched on.
DIMENSION_MEMORY = (4, 16, 32, 64)

#: What each of those totals is made of, bank by bank.
DIMENSION_BANKS = {
    0: (0, 0, 0, 0),
    4: (4, 0, 0, 0),
    16: (16, 0, 0, 0),
    32: (16, 16, 0, 0),
    64: (16, 16, 16, 16),
}

#: Where the console is drawn. Zero is the machine's own screen, and any other
#: value is the slot of the board that draws it. Previous masks this with 6, so
#: only 0, 2, 4 and 6 mean anything.
CONSOLE_ON_THE_MACHINE = 0

#: How Previous lays its screens out: one screen in its one window, which is
#: SCREEN_SINGLE, the first value of SCREENMODE in its
#: src/includes/configuration.h. Which screen that is goes into
#: nSingleModeSlot, numbered like nConsoleSlot.
ONE_SCREEN = 0

#: A machine with no board in any slot, and one with a single 32 MB board in the
#: first, which is what the emulator's own file holds for a NeXTdimension.
NO_BOARDS = (0,) * DIMENSION_BOARDS
ONE_BOARD = (32,) + (0,) * (DIMENSION_BOARDS - 1)

#: The 1988 machine, the cube and the station, as Previous numbers them in
#: nMachineType. Everything below is decided by which of the three it is.
NEXT_COMPUTER = 0
NEXTCUBE = 1
NEXTSTATION = 2

#: Which sizes one memory bank accepts, in megabytes, by what the machine is.
#: From Configuration_CheckMemory in Previous's src/configuration.c, which asks
#: in this order: a turbo board decides first, then color, then what is left.
#: Anything in between is rounded up to the next of these and anything above
#: the largest is capped at it.
TURBO_BANK_SIZES = (0, 2, 8, 32)
COLOUR_BANK_SIZES = (0, 2, 8)
PLAIN_BANK_SIZES = (0, 1, 4, 16)

#: How many banks the machine holds, and how many of them a NeXTstation without
#: a turbo board and without color can reach. On that board the other two are
#: not physically there, and Previous empties them at every start rather than
#: when the machine is chosen, so a file that fills them is corrected under
#: whoever wrote it.
BANKS = 4
STATION_PLAIN_BANKS = 2

#: The bank a machine boots from, and the least it must hold to do it, in
#: megabytes. Previous says so on the face of its own memory dialog: "For
#: booting Bank0 must contain at least 4 MB of memory."
#:
#: The emulator does not enforce it, because the check that would is compiled
#: out: `RESTRICTIVE_MEMCHECK` is 0 in its src/configuration.c. This editor does
#: enforce it, since a machine that cannot boot is not one worth building, so
#: that bank is offered no size below this and no empty bank at all.
#:
#: Nothing is enforced about a gap further along. Previous corrects one only on
#: a NeXTdimension board, where its own comment says an empty first bank with
#: memory behind it panics the kernel, and it says nothing of the kind about the
#: machine's own memory.
FIRST_BANK = 0
BOOTABLE_BANK_MB = 4

#: The ones with a default carry what Previous starts every machine from, or
#: what NeXT fitted as standard, so the catalog below names them only where
#: one of the eleven differs.
#:
#: `floppy`, `optical` and `printer` say whether the machine has that drive or
#: that port at all, rather than what is in it. A disk image is the
#: installation's business and none of this tool's.
#:
#: `dimensions` is how much memory each of the three NeXTdimension boards has,
#: in slot order, and zero is a slot with no board in it. One value rather than a
#: board and a size apart, because a board Previous would give memory to is a
#: board with memory.
Machine = collections.namedtuple(
    "Machine",
    "identifier name kind turbo mhz colour dimensions banks"
    " dsp dsp_memory"
    " floppy optical ethernet socket printer",
    defaults=(DSP_PLAIN, DSP_MEMORY_EXPANDED,
              True, False, True, THIN_WIRE, False))

#: Every machine that can be chosen, in the order they were built.
#:
#: `banks` is the four memory banks in megabytes. These are data rather than a
#: rule: a turbo takes 32 MB modules and an early station was sold with two
#: banks filled, and no arithmetic connects those facts.
#:
#: `mhz` is the same kind of fact. The two Nitros are the machines NeXT clocked
#: at 40, and everything else runs at what its boards give it.
#:
#: The 1988 machine is the one whose DSP has no expansion memory, which is what
#: Configuration_SetSystemDefaults says about it and the only place these eleven
#: differ in their DSP at all.
CATALOGUE = (
    Machine("next-computer", "NeXT Computer", NEXT_COMPUTER,
            turbo=False, mhz=PLAIN_MHZ, colour=False, dimensions=NO_BOARDS,
            banks=(16, 16, 16, 16), dsp_memory=DSP_MEMORY_PLAIN,
            # The 1988 machine is the one NeXT sold with the optical drive and
            # no floppy at all.
            floppy=False, optical=True),
    Machine("nextcube", "NeXTcube", NEXTCUBE,
            turbo=False, mhz=PLAIN_MHZ, colour=False, dimensions=NO_BOARDS,
            banks=(16, 16, 16, 16)),
    Machine("nextcube-dimension", "NeXTcube mit NeXTdimension", NEXTCUBE,
            turbo=False, mhz=PLAIN_MHZ, colour=False, dimensions=ONE_BOARD,
            banks=(16, 16, 16, 16)),
    Machine("nextcube-turbo", "NeXTcube Turbo", NEXTCUBE,
            turbo=True, mhz=TURBO_MHZ, colour=False, dimensions=NO_BOARDS,
            banks=(32, 32, 32, 32)),
    Machine("nextcube-turbo-dimension", "NeXTcube Turbo mit NeXTdimension", NEXTCUBE,
            turbo=True, mhz=TURBO_MHZ, colour=False, dimensions=ONE_BOARD,
            banks=(32, 32, 32, 32)),
    Machine("nextcube-turbo-nitro", "NeXTcube Turbo Nitro", NEXTCUBE,
            turbo=True, mhz=NITRO_MHZ, colour=False, dimensions=NO_BOARDS,
            banks=(32, 32, 32, 32)),
    Machine("nextstation", "NeXTstation", NEXTSTATION,
            turbo=False, mhz=PLAIN_MHZ, colour=False, dimensions=NO_BOARDS,
            banks=(16, 16, 0, 0)),
    Machine("nextstation-color", "NeXTstation Color", NEXTSTATION,
            turbo=False, mhz=PLAIN_MHZ, colour=True, dimensions=NO_BOARDS,
            banks=(8, 8, 8, 8)),
    Machine("nextstation-turbo", "NeXTstation Turbo", NEXTSTATION,
            turbo=True, mhz=TURBO_MHZ, colour=False, dimensions=NO_BOARDS,
            banks=(32, 32, 32, 32)),
    Machine("nextstation-turbo-color", "NeXTstation Turbo Color", NEXTSTATION,
            turbo=True, mhz=TURBO_MHZ, colour=True, dimensions=NO_BOARDS,
            banks=(32, 32, 32, 32)),
    Machine("nextstation-turbo-color-nitro", "NeXTstation Turbo Color Nitro", NEXTSTATION,
            turbo=True, mhz=NITRO_MHZ, colour=True, dimensions=NO_BOARDS,
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
    none of this function's business. A disk image is the clearest case of that:
    whether a drive is there is the machine, and what is in it is not.
    """
    return {
        "System": _system_for(machine),
        "Dimension": _dimension_for(machine),
        "Memory": {
            **{
                "nMemoryBankSize%d" % index: str(size)
                for index, size in enumerate(machine.banks)
            },
            "nMemorySpeed": str(MEMORY_SPEED),
        },
        # One drive of each kind, because that is what NeXT built, and the rest
        # written as absent rather than left at whatever the last machine had.
        "Floppy": _drives(machine.floppy, FLOPPY_DRIVES),
        "MagnetoOptical": _drives(machine.optical, OPTICAL_DRIVES),
        "Ethernet": {
            "bEthernetConnected": _flag(machine.ethernet),
            "bTwistedPair": _flag(
                machine.ethernet and machine.socket == TWISTED_PAIR),
        },
        "Printer": {"bPrinterConnected": _flag(machine.printer)},
    }


def _dimension_for(machine):
    """The Dimension section, which is three boards rather than one.

    @param machine - A Machine.
    @returns dict of key to value, all strings.

    Every slot is written, so a board taken out says so rather than being left
    at whatever the last machine had. `bI860Thread` is not written at all:
    Configuration_CheckDimensionSettings sets it from how many processors the
    host has, so it belongs to the machine the emulator runs on rather than to
    the one it emulates.
    """
    written = {}
    for board, memory in enumerate(machine.dimensions):
        written["bEnabled%d" % board] = _flag(bool(memory))
        for bank, size in enumerate(DIMENSION_BANKS[memory]):
            written["nMemoryBankSize%d%d" % (board, bank)] = str(size)
    written["nConsoleSlot"] = str(console_slot(machine.dimensions))
    return written


def _drives(fitted, most):
    """Which drives of one kind the machine has.

    @param fitted - Whether it has one at all.
    @param most - How many of them Previous keeps in its file.
    @returns dict of key to the word Previous writes for a boolean.
    """
    return {
        "bDriveConnected%d" % drive: _flag(fitted and drive == 0)
        for drive in range(most)
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
    @param color - Whether the color board is, the same way.
    @returns tuple of four tuples of megabytes, one per bank in the order they
      sit in. A bank the machine cannot reach offers nothing but zero, which is
      a choice of one rather than an absence, so whatever draws this has four
      banks to draw either way.

    Taking the two flags rather than a Machine, because they have to be the
    settled ones: a cube with color asked for is a cube without it, and
    reading a bank rule off a choice the emulator refuses would offer sizes no
    machine has.

    The first bank is the one that cannot be empty. Previous says so on the face
    of its own memory dialog, and the editor holds the machine to it rather
    than warning about it afterwards, because a machine that cannot boot is not
    one worth building.
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

    return tuple(_sizes_for(sizes, bank, reachable) for bank in range(BANKS))


def _sizes_for(sizes, bank, reachable):
    """What one bank accepts.

    @param sizes - What a bank of this machine takes, empty first.
    @param bank - Which of the four, from 0.
    @param reachable - How many of them the machine has.
    @returns tuple of int
    """
    if bank >= reachable:
        return (0,)
    if bank == FIRST_BANK:
        return tuple(size for size in sizes if size >= BOOTABLE_BANK_MB)
    return sizes


#: What a total of memory is made of, bank by bank, in megabytes. From
#: `defmemsize` in Previous's src/gui-sdl/dlgAdvanced.c, which is the table its
#: own dialog fills the four banks from when somebody picks a size there.
#:
#: Two families, because the same total is laid out differently: a plain
#: monochrome machine takes 16 MB modules and anything with a turbo board or a
#: color board takes 8 and 32 MB ones.
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
#: dialog, which takes the larger two away where the board cannot hold them:
#: 128 MB wants a turbo board, and 64 MB wants either that or the four banks a
#: monochrome cube has.
TURBO_MEMORY = (8, 16, 32, 64, 128)
CUBE_MEMORY = (8, 16, 32, 64)
NARROW_MEMORY = (8, 16, 32)


def memory_totals(kind, turbo, colour):
    """How much memory this machine can be given, in megabytes.

    @param kind - NEXT_COMPUTER, NEXTCUBE or NEXTSTATION.
    @param turbo - Whether a turbo board is seated, as settled() leaves it.
    @param color - Whether the color board is, the same way.
    @returns tuple of int, smallest first.

    A total rather than four banks, because that is what Previous's own dialog
    offers and what a person means by how much memory a machine has. Which
    modules make it up follows from the machine, and PLAIN_MEMORY and
    WIDE_MEMORY are that.
    """
    if turbo:
        return TURBO_MEMORY
    if colour or kind == NEXTSTATION:
        # A color board takes 8 MB modules and fills all four banks at 32, and
        # a plain station reaches only two banks at all. Both stop at 32.
        return NARROW_MEMORY
    return CUBE_MEMORY


def banks_for(total, kind, turbo, colour):
    """The four banks a total of memory is made up of.

    @param total - How much memory, in megabytes.
    @param kind - The machine type.
    @param turbo - Whether a turbo board is seated, as settled() leaves it.
    @param color - Whether the color board is, the same way.
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


def clocks_for(turbo):
    """Which clocks this machine can be run at, in megahertz.

    @param turbo - Whether a turbo board is seated, as settled() leaves it.
    @returns tuple of int, slowest first.

    Previous offers the same four for every machine and adds the fastest only
    where that board is in, which is what its own dialog does by replacing the
    40 MHz option with blank space.
    """
    return (CLOCKS + (NITRO_MHZ,)) if turbo else CLOCKS


def default_clock(turbo):
    """What a machine runs at when the one it held is not one it can have.

    @param turbo - Whether a turbo board is seated.
    @returns int

    Previous writes this whenever the machine type or that board changes in its
    own dialog, and never checks the clock at start. So a clock that does not
    belong to the machine is not corrected there, it is replaced the moment
    somebody touches what decides it, and this is the same act.
    """
    return TURBO_MHZ if turbo else PLAIN_MHZ


def default_dsp_memory(kind):
    """How much memory the DSP has where nothing else has been chosen.

    @param kind - NEXT_COMPUTER, NEXTCUBE or NEXTSTATION.
    @returns int, in kilobytes.

    The 1988 machine is the one without the expansion, and
    Configuration_SetSystemDefaults writes that difference every time the
    machine type changes in Previous's own dialog.
    """
    return DSP_MEMORY_PLAIN if kind == NEXT_COMPUTER else DSP_MEMORY_EXPANDED


def takes_a_floppy(kind):
    """Whether this machine has a floppy drive at all.

    @param kind - NEXT_COMPUTER, NEXTCUBE or NEXTSTATION.
    @returns bool

    NeXT's 1988 machine shipped with the optical drive and no floppy, which is
    what Previous's own Floppy dialog says on its face. The emulator does not
    enforce it: with a drive connected there, `floppy_controller_present` in its
    src/floppy.c answers that the controller is there. So this is our rule, and
    it is here because the editor builds machines that were built.
    """
    return kind != NEXT_COMPUTER


def takes_an_optical_drive(kind, turbo):
    """Whether this machine has a magneto-optical drive at all.

    @param kind - NEXT_COMPUTER, NEXTCUBE or NEXTSTATION.
    @param turbo - Whether a turbo board is seated, as settled() leaves it.
    @returns bool

    The cubes had it and the turbo boards dropped it, which is what Previous's
    own Optical dialog says on its face. Not enforced there either, for the
    same reason as the floppy above.
    """
    return kind != NEXTSTATION and not turbo


def takes_twisted_pair(kind):
    """Whether this machine has the twisted pair ethernet socket.

    @param kind - NEXT_COMPUTER, NEXTCUBE or NEXTSTATION.
    @returns bool

    The 1988 machine has the coaxial socket alone, and this one Previous does
    enforce: `Configuration_CheckEthernetSettings` switches twisted pair off for
    that machine type at every start.
    """
    return kind != NEXT_COMPUTER


def dimension_slot(board):
    """Which slot a NeXTdimension board answers from.

    @param board - Which of the three, from 0.
    @returns int, so 2, 4 or 6. From ND_SLOT in Previous's
      src/dimension/dimension.hpp.
    """
    return board * 2 + 2


def takes_a_dimension(kind):
    """Whether this machine can hold a NeXTdimension at all.

    @param kind - NEXT_COMPUTER, NEXTCUBE or NEXTSTATION.
    @returns bool

    The board speaks on the NeXTbus and a NeXTstation has none, so
    Configuration_CheckDimensionSettings switches every board off for that
    machine type at every start.
    """
    return kind != NEXTSTATION


def console_slot(dimensions):
    """Which slot draws the console.

    @param dimensions - How much memory each board has, in slot order.
    @returns int, the slot of the first board there is, or
      CONSOLE_ON_THE_MACHINE where there is none.

    The first rather than a choice of its own. Previous keeps that choice, and a
    machine with two graphics boards where the second draws the console is a
    thing to put in front of somebody only once the first is worth having.
    """
    for board, memory in enumerate(dimensions):
        if memory:
            return dimension_slot(board)
    return CONSOLE_ON_THE_MACHINE


def screen_for(machine):
    """Which screen Previous shows in its window: the one the console is on.

    @param machine - A Machine.
    @returns dict of key to value for the Screen section, all strings.

    Previous keeps the two apart. nConsoleSlot is where the ROM and NeXTSTEP
    draw, and nSingleModeSlot is what the window shows, which is the CPU
    board's own screen unless it says otherwise. Its own Graphics dialog sets
    both together when "Color" is chosen, in src/gui-sdl/dlgGraphics.c, and
    this does the same. A machine with its console on a NeXTdimension would
    otherwise show the CPU board's screen while everything is drawn on the
    board.
    """
    return {"nMode": str(ONE_SCREEN),
            "nSingleModeSlot": str(console_slot(machine.dimensions))}


def written_for(machine):
    """Everything written into previous.cfg when a machine is started.

    @param machine - A Machine.
    @returns dict of section name to dict of key to value, as `settings_for`
      answers, with the Screen section from `screen_for` beside it.

    Two answers rather than one, because `settings_for` is also what a file is
    matched against to say which machine it is, and which screen the window
    shows does not make it a different machine.
    """
    return dict(settings_for(machine), Screen=screen_for(machine))


def _dimensions_settled(dimensions, kind):
    """The three boards a machine of this type would actually have.

    @param dimensions - How much memory each was asked to have, in slot order.
      A shorter list is read as empty slots after it, and a longer one is cut,
      which is what a hand-written file can hold.
    @param kind - The machine type.
    @returns tuple of DIMENSION_BOARDS ints.

    A size the board does not take becomes the largest it does that is no
    bigger, which is how Configuration_CheckDimensionMemory rounds a bank, and
    anything below the smallest is no board at all.
    """
    if not takes_a_dimension(kind):
        return NO_BOARDS

    wanted = tuple(dimensions) + NO_BOARDS
    return tuple(_dimension_memory(wanted[board])
                 for board in range(DIMENSION_BOARDS))


def _dimension_memory(memory):
    """One board's memory, held to a size it can have.

    @param memory - What was asked for, in megabytes.
    @returns int, and zero for no board at all.
    """
    wanted = whole(memory, 0)
    fits = [size for size in DIMENSION_MEMORY if size <= wanted]
    return fits[-1] if fits else 0


def drafted(kind, turbo=False, colour=False, dimensions=NO_BOARDS,
            mhz=None, memory=None, banks=None, dsp=None, dsp_memory=None,
            floppy=False, optical=False, ethernet=False,
            socket=None, printer=False, identifier="", name=""):
    """A machine from what an editor is showing, held to Previous's rules.

    @param kind - The machine type, as a number or a string of one.
    @param turbo - Whether a turbo board is asked for.
    @param color - Whether the color board is.
    @param dimensions - How much memory each NeXTdimension board has, in
      slot order, as a sequence or as a string of comma separated numbers.
      A slot with no board in it is zero.
    @param mhz - The clock asked for, in megahertz.
    @param memory - How much memory, as a total in megabytes.
    @param banks - The four banks, where they were chosen one at a time, as a
      sequence or as a string of comma separated numbers. Given these, the total
      follows from them and `memory` is not read.
    @param dsp - Which DSP, as one of DSPS.
    @param dsp_memory - How much memory it has, in kilobytes.
    @param floppy - Whether the machine has a floppy drive.
    @param optical - Whether it has a magneto-optical drive.
    @param ethernet - Whether it is on the network.
    @param socket - Which ethernet socket, as one of ETHERNET_SOCKETS.
    @param printer - Whether the printer port is in use.
    @param identifier - What it is called to the API, where it has a name.
    @param name - What it is called to a person.
    @returns Machine, settled.

    These are the controls an editor draws, one each, and nothing about them is
    a rule: which of them may be chosen at all is offers(), and what they turn
    into is here and in settled(). So an interface holds no copy of anything
    Previous decides.

    The clock and the two about the DSP arrive as nothing at all whenever an
    editor has just changed the machine type or a board, because Previous writes
    all three afresh at both of those moments. Each then comes back as what this
    machine has rather than as what the last one did.

    Nitro is not one of them. Previous has no such thing and reads nCpuFreq as
    it finds it, so a clock of 40 is what the catalog calls a Nitro and that is
    the direction the translation runs in.
    """
    wanted = _sizes_asked_for(banks)
    machine = settled(Machine(
        identifier=identifier,
        name=name,
        kind=whole(kind, NEXTCUBE),
        turbo=bool(turbo),
        # Zero is no clock, which is what nothing at all arrives as. It is not
        # one the machine can be offered, so settled() replaces it.
        mhz=whole(mhz, 0),
        colour=bool(colour),
        dimensions=_sizes_asked_for(dimensions) or NO_BOARDS,
        banks=wanted or (0, 0, 0, 0),
        # And a DSP nobody named is not one of the three, for the same reason.
        dsp=dsp if dsp in DSPS else "",
        dsp_memory=whole(dsp_memory, 0),
        floppy=bool(floppy),
        optical=bool(optical),
        ethernet=bool(ethernet),
        socket=socket if socket in ETHERNET_SOCKETS else THIN_WIRE,
        printer=bool(printer),
    ))
    if wanted is not None:
        return machine
    # The total, where no bank was named on its own. After the flags, because
    # they decide which totals there are and what each one is made of.
    return machine._replace(
        banks=banks_for(memory, machine.kind, machine.turbo, machine.colour))


def _sizes_asked_for(sizes):
    """A run of sizes an editor named one at a time.

    @param sizes - A sequence of numbers, or a string of comma separated ones,
      which is how they arrive on a query string. Nothing at all where the
      editor said nothing about them.
    @returns tuple of int, or None where nothing was named. Anything that is not
      a number is zero, which `settled` then holds to a size the machine takes.

    The four memory banks and the three NeXTdimension boards both arrive this
    way, because both are a row of sizes in one field.
    """
    if sizes is None or sizes == "":
        return None
    if isinstance(sizes, str):
        sizes = sizes.split(",")
    return tuple(whole(size, 0) for size in sizes)


def offers(machine):
    """What may be chosen for a machine like this one.

    @param machine - A Machine, settled.
    @returns dict, one entry per control an editor draws: the machine types,
      whether the turbo board, the color board and a NeXTdimension may be
      seated at all, which clocks there are, and which totals of memory.

    Answered by the service rather than worked out in the browser, so there is
    one statement of what Previous allows and an interface cannot offer a
    machine the emulator would correct underneath it.

    A machine type carries its number and its name together, because a cell is
    labeled with the one and chosen by the other. The name is the emulator's
    own and is not translated anywhere, which is why it travels from here rather
    than being a word the interface holds.

    The clocks are numbers here and strings in the file, because a browser
    compares them against what somebody chose and the file holds text.
    """
    return {
        "kinds": [{"kind": kind, "model": config.MACHINE_NAMES[kind]}
                  for kind in (NEXT_COMPUTER, NEXTCUBE, NEXTSTATION)],
        "turbo": machine.kind != NEXT_COMPUTER,
        "colour": machine.kind == NEXTSTATION,
        # Which slots can hold a NeXTdimension, and how much memory one of them
        # takes. Three slots on a cube and none on a station.
        "dimension_slots": ([dimension_slot(board)
                             for board in range(DIMENSION_BOARDS)]
                            if takes_a_dimension(machine.kind) else []),
        "dimension_memory": list(DIMENSION_MEMORY),
        "clocks": list(clocks_for(machine.turbo)),
        "memory": list(memory_totals(
            machine.kind, machine.turbo, machine.colour)),
        # What each of the four banks takes on its own, for somebody who wants a
        # machine no total adds up to. A bank that is not there offers nothing
        # but an empty one, so there are always four to draw.
        "banks": [list(sizes) for sizes in bank_sizes(
            machine.kind, machine.turbo, machine.colour)],
        "dsps": list(DSPS),
        # Nothing to choose between where there is no chip to give it to, and a
        # group with nothing to offer is not drawn.
        "dsp_memory": [] if machine.dsp == DSP_NONE else list(DSP_MEMORIES),
        # What the machine can have fitted. Ethernet and the printer port are on
        # every one of them, so those two are always there to switch.
        "floppy": takes_a_floppy(machine.kind),
        "optical": takes_an_optical_drive(machine.kind, machine.turbo),
        "ethernet": True,
        "printer": True,
        # Nothing to choose between where the machine is off the network, and a
        # group with nothing to offer is not drawn.
        "sockets": [socket for socket in ETHERNET_SOCKETS
                    if machine.ethernet
                    and (socket != TWISTED_PAIR
                         or takes_twisted_pair(machine.kind))],
    }


def settled(machine):
    """The machine Previous would run, given what somebody put together.

    @param machine - A Machine, which may hold a choice the emulator does not
      allow: color on a cube, a board in a station, memory in a bank that is
      not there.
    @returns Machine, identical in everything Previous accepts and corrected in
      everything it does not.

    Previous never refuses a configuration. It corrects one, in two places, and
    both are in its src/configuration.c. Its own dialog runs
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
        # The clock and the DSP are the values Previous does not check at start.
        # Its own dialog writes all three afresh every time the machine type or
        # a board changes, so a machine holding one it cannot be offered gets
        # what that machine actually has.
        mhz=machine.mhz if machine.mhz in clocks_for(turbo) else default_clock(turbo),
        colour=colour,
        # Every board goes on a machine with no NeXTbus, and a size the board
        # does not take becomes the nearest it does, which is what
        # Configuration_CheckDimensionSettings and Configuration_CheckDimensionMemory
        # do at every start.
        dimensions=_dimensions_settled(machine.dimensions, machine.kind),
        banks=tuple(_bank(wanted[bank], sizes[bank]) for bank in range(BANKS)),
        dsp=machine.dsp if machine.dsp in DSPS else DSP_PLAIN,
        dsp_memory=(machine.dsp_memory if machine.dsp_memory in DSP_MEMORIES
                    else default_dsp_memory(machine.kind)),
        # A drive the machine never had goes, the way a board it cannot hold
        # does. Previous enforces neither of these two and says both on the face
        # of its own dialogs.
        floppy=machine.floppy and takes_a_floppy(machine.kind),
        optical=machine.optical and takes_an_optical_drive(machine.kind, turbo),
        # And the socket the 1988 machine has none of, which
        # Configuration_CheckEthernetSettings does switch off at every start.
        socket=(machine.socket
                if machine.socket in ETHERNET_SOCKETS
                and (machine.socket != TWISTED_PAIR
                     or takes_twisted_pair(machine.kind))
                else THIN_WIRE),
    )


def _system_for(machine):
    """The System section, which is where a machine is really decided.

    @param machine - A Machine.
    @returns dict of key to value, all strings.

    Every value here follows from the type, the turbo board and the color
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
        # a color station, while everything else has the MC68HC68T1. Previous
        # writes the choice as a boolean, and TRUE is the MCCS1850.
        "nRTC": _flag(machine.turbo or (machine.kind == NEXTSTATION and machine.colour)),
        # The SCSI controller, as a boolean the same way: the 1988 machine has
        # the NCR53C90 and every 68040 the NCR53C90A.
        "nSCSI": _flag(not is_1988),
        # The NeXTbus interface chip sits in the cubes, which have a bus, and
        # not in the station, which has none.
        "bNBIC": _flag(machine.kind != NEXTSTATION),
        "nDSPType": DSP_TYPES[machine.dsp],
        # Written as a flag, and the expansion is what the larger of the two
        # sizes is.
        "bDSPMemoryExpansion": _flag(
            machine.dsp_memory == DSP_MEMORY_EXPANDED),
    }


def _clock(machine):
    """@returns The clock in megahertz, as the file holds it."""
    return str(machine.mhz)


def _bank(size, sizes):
    """One memory bank, held to a size the machine accepts.

    @param size - What was asked for, in megabytes.
    @param sizes - What that bank offers, as bank_sizes answers.
    @returns int

    Rounded up to the next size offered and capped at the largest, which is what
    Configuration_CheckMemory does: three megabytes on a turbo board is a bank of
    eight, and sixty-four is a bank of thirty-two. Anything that is not a number
    at all, which a hand-edited file can hold, is an empty bank.

    Except where the bank is not offered an empty one, which is the first, since
    the machine boots from it. Asked to empty that one, it holds the least it
    can instead.
    """
    try:
        wanted = int(size)
    except (TypeError, ValueError):
        wanted = 0
    if wanted <= 0:
        return 0 if 0 in sizes else sizes[0]
    for offered in sizes:
        if wanted <= offered:
            return offered
    return sizes[-1]


def _flag(value):
    """@returns The word Previous writes for a boolean."""
    return "TRUE" if value else "FALSE"
