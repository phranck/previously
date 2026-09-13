"""Reading previous.cfg, the emulator's own configuration.

The file is INI-shaped, so configparser reads it. What this module adds is the
knowledge of what the values mean, because the file says `nMachineType = 1` and
a person wants to be told `NeXTcube`.

Nothing here writes. Writing is the risky half and lives on its own, so that
the half which only looks cannot damage anything.
"""

import configparser

#: What the emulator calls each machine, by the number in the file. The names
#: are Previous's own, from its machine type enumeration.
MACHINE_NAMES = {
    0: "NeXT Computer",
    1: "NeXTcube",
    2: "NeXTstation",
}

#: The processor each level stands for. Previous stores a level rather than a
#: name, and sets it itself from the machine type.
CPU_NAMES = {
    0: "68030",
    1: "68040",
    2: "68040",
    3: "68040",
    4: "68040",
}


class NotReadable(Exception):
    """The configuration file is absent or cannot be parsed."""


def read(path):
    """Reads previous.cfg and reports what the emulated machine is set to.

    @param path - pathlib.Path to previous.cfg.
    @returns dict with the machine, its processor, memory, disk and screen.
    @raises NotReadable - The file is not there, or is not INI-shaped.
    """
    parser = configparser.ConfigParser()
    parser.optionxform = str          # the file's keys are case sensitive
    try:
        if not parser.read(path):
            raise NotReadable("no such file: %s" % path)
    except configparser.Error as error:
        raise NotReadable(str(error)) from error

    system = _section(parser, "System")
    memory = _section(parser, "Memory")
    dimension = _section(parser, "Dimension")

    machine_type = _int(system, "nMachineType", 1)
    turbo = _bool(system, "bTurbo")
    dimension_seated = _bool(dimension, "bEnabled0")

    return {
        "machine": _machine_name(machine_type, turbo, dimension_seated),
        "cpu": _cpu(system),
        "memory_mb": _memory(memory),
        "screen": _screen(system, dimension_seated),
        "disk": _disk(parser),
        "dimension": dimension_seated,
    }


def _section(parser, name):
    """@returns The section as a mapping, empty where the file has none."""
    return parser[name] if parser.has_section(name) else {}


def _int(section, key, fallback=0):
    try:
        return int(section.get(key, fallback))
    except (TypeError, ValueError):
        return fallback


def _bool(section, key):
    return str(section.get(key, "FALSE")).strip().upper() == "TRUE"


def _machine_name(machine_type, turbo, dimension_seated):
    """The name a person would use, which the file does not hold anywhere.

    Previous stores the type, the turbo flag and the board separately, and the
    machine somebody means is all three together.
    """
    name = MACHINE_NAMES.get(machine_type, "unbekannt")
    if turbo and machine_type in (1, 2):
        name += " Turbo"
    if dimension_seated:
        name += " mit NeXTdimension"
    return name


def _cpu(system):
    """@returns The processor and its clock, as one readable string."""
    level = _int(system, "nCpuLevel", 1)
    clock = _int(system, "nCpuFreq", 25)
    return "%s, %d MHz" % (CPU_NAMES.get(level, "68040"), clock)


def _memory(memory):
    """@returns Total memory in megabytes, summed over the banks.

    Previous holds four banks and the machine has as much as they add up to.
    """
    return sum(_int(memory, "nMemoryBankSize%d" % bank) for bank in range(4))


def _screen(system, dimension_seated):
    """What the screen shows, which is where colour is decided.

    A cube has no colour of its own: Previous forces bColor false for that
    machine type, and colour arrives only through a NeXTdimension.
    """
    if dimension_seated:
        return "NeXTdimension, farbig"
    return "MegaPixel, farbig" if _bool(system, "bColor") else "MegaPixel, Graustufen"


def _disk(parser):
    """@returns The name of the disk the machine boots from, or None.

    The first SCSI slot holding an inserted disk is the one that matters; the
    file keeps seven and leaves the rest empty.
    """
    disks = _section(parser, "HardDisk")
    for slot in range(7):
        if _bool(disks, "bDiskInserted%d" % slot):
            path = disks.get("szImageName%d" % slot, "")
            return path.rsplit("/", 1)[-1] or None
    return None


def write(path, settings):
    """Applies settings to the file, leaving everything else exactly as it was.

    @param path - The configuration to change.
    @param settings - Section name to key to value, as machines.settings_for
      returns. Only these keys are touched.
    @returns int, how many lines were changed.
    @raises NotReadable where the file cannot be read or written.

    Line by line rather than through configparser, which would rewrite the
    whole file from its own idea of the format and drop anything it does not
    model. Previous keeps 234 lines here and this tool understands ten of them,
    so the other 224 are none of its business and are passed through untouched.

    The section has to be tracked whilst walking, because the same key name
    appears in more than one of them. nMemoryBankSize0 is the machine's first
    memory bank under [Memory], and [Dimension] carries its own board memory
    under names that begin the same way.
    """
    try:
        lines = path.read_text().splitlines(keepends=True)
    except OSError as error:
        raise NotReadable("cannot read %s: %s" % (path, error)) from error

    wanted = {section: dict(keys) for section, keys in settings.items()}
    changed = 0
    section = None
    out = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped[1:-1]
        elif section in wanted and "=" in line:
            key = line.split("=", 1)[0].strip()
            if key in wanted[section]:
                value = wanted[section].pop(key)
                replacement = "%s = %s\n" % (key, value)
                if replacement != line:
                    changed += 1
                line = replacement
        out.append(line)

    # Anything the file did not already carry. Previous writes every key it
    # knows, so this is for a file somebody has trimmed by hand.
    for name, remaining in wanted.items():
        if remaining:
            out.extend(_appended(name, remaining, out))
            changed += len(remaining)

    try:
        path.write_text("".join(out))
    except OSError as error:
        raise NotReadable("cannot write %s: %s" % (path, error)) from error
    return changed


def _appended(name, keys, out):
    """The lines for keys whose section did not hold them.

    @param name - The section they belong to.
    @param keys - What is left over.
    @param out - The lines written so far, so an existing section is found.
    @returns list of lines to add at the end.

    Appended rather than inserted into the section where it sits, because a
    file that is missing a key Previous always writes is a file somebody has
    edited, and moving their lines about would be a second surprise.
    """
    lines = []
    if "[%s]" % name not in "".join(out):
        lines.append("\n[%s]\n" % name)
    lines.extend("%s = %s\n" % (key, value) for key, value in keys.items())
    return lines


def back_up(path):
    """Copies the file beside itself, so the last change can be undone.

    @param path - The configuration.
    @returns pathlib.Path of the copy.
    @raises NotReadable where it cannot be made.

    One generation, replaced on each write. What gets undone is always the last
    change, and a directory of dated copies is a tidiness problem nobody asked
    for.
    """
    copy = path.with_suffix(path.suffix + ".bak")
    try:
        copy.write_bytes(path.read_bytes())
    except OSError as error:
        raise NotReadable("cannot back up %s: %s" % (path, error)) from error
    return copy
