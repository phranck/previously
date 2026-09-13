"""Which machines can be configured, and what each one is in the file.

A machine is not one setting. Choosing a NeXTcube Turbo means a machine type, a
processor level, a clock, whether the colour board is seated, which slot it
speaks from, and four memory banks, and getting one of them wrong produces a
machine that either will not boot or is not the machine that was asked for.
Previous's own dialogue moves them together when the type changes there, and
this does the same.

The values come from the eleven ready-made configurations in the project's
Papers folder, which were compared key by key on 13 September 2026. Ten of
their 195 keys differ between machines, and those ten are what is below.
Everything else in previous.cfg is the same whichever machine is chosen and is
left exactly as it stands.
"""

import collections

#: The processor in every machine this emulates. NeXT's own line moved to the
#: 68040 with the cube, and Previous models nothing earlier that boots this
#: disk, so this is a constant rather than a choice.
CPU_LEVEL = "4"

#: The clock of a machine without the Nitro option, and with it. Nitro was a
#: faster turbo board rather than a different machine, so it shows up here and
#: nowhere else.
CLOCK_MHZ = "33"
NITRO_MHZ = "40"

#: Which slot a NeXTdimension board answers from. Zero means no board.
DIMENSION_SLOT = "2"
NO_BOARD = "0"

Machine = collections.namedtuple(
    "Machine", "identifier name kind turbo nitro colour dimension banks")

#: Every machine that can be chosen, in the order they were built.
#:
#: `kind` is what Previous calls nMachineType: 0 is the 1988 NeXT Computer, 1
#: the cube, 2 the station.
#:
#: `banks` is the four memory banks in megabytes. These are data rather than a
#: rule: a turbo takes 32 MB modules and an early station was sold with two
#: banks filled, and no arithmetic connects those facts.
CATALOGUE = (
    Machine("next-computer", "NeXT Computer", 0,
            turbo=False, nitro=False, colour=False, dimension=False,
            banks=(16, 16, 16, 16)),
    Machine("nextcube", "NeXTcube", 1,
            turbo=False, nitro=False, colour=False, dimension=False,
            banks=(16, 16, 16, 16)),
    Machine("nextcube-dimension", "NeXTcube mit NeXTdimension", 1,
            turbo=False, nitro=False, colour=False, dimension=True,
            banks=(16, 16, 16, 16)),
    Machine("nextcube-turbo", "NeXTcube Turbo", 1,
            turbo=True, nitro=False, colour=False, dimension=False,
            banks=(32, 32, 32, 32)),
    Machine("nextcube-turbo-dimension", "NeXTcube Turbo mit NeXTdimension", 1,
            turbo=True, nitro=False, colour=False, dimension=True,
            banks=(32, 32, 32, 32)),
    Machine("nextcube-turbo-nitro", "NeXTcube Turbo Nitro", 1,
            turbo=True, nitro=True, colour=False, dimension=False,
            banks=(32, 32, 32, 32)),
    Machine("nextstation", "NeXTstation", 2,
            turbo=False, nitro=False, colour=False, dimension=False,
            banks=(16, 16, 0, 0)),
    Machine("nextstation-color", "NeXTstation Color", 2,
            turbo=False, nitro=False, colour=True, dimension=False,
            banks=(8, 8, 8, 8)),
    Machine("nextstation-turbo", "NeXTstation Turbo", 2,
            turbo=True, nitro=False, colour=False, dimension=False,
            banks=(32, 32, 32, 32)),
    Machine("nextstation-turbo-color", "NeXTstation Turbo Color", 2,
            turbo=True, nitro=False, colour=True, dimension=False,
            banks=(32, 32, 32, 32)),
    Machine("nextstation-turbo-color-nitro", "NeXTstation Turbo Color Nitro", 2,
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
        "System": {
            "nMachineType": str(machine.kind),
            "nCpuLevel": CPU_LEVEL,
            "nCpuFreq": NITRO_MHZ if machine.nitro else CLOCK_MHZ,
            "bTurbo": _flag(machine.turbo),
            "bColor": _flag(machine.colour),
        },
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


def _flag(value):
    """@returns The word Previous writes for a boolean."""
    return "TRUE" if value else "FALSE"
