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


def _flag(value):
    """@returns The word Previous writes for a boolean."""
    return "TRUE" if value else "FALSE"
