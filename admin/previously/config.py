"""Reading previous.cfg, the emulator's own configuration.

The file is INI-shaped, so configparser reads it. What this module adds is the
knowledge of what the values mean, because the file says `nMachineType = 1` and
a person wants to be told `NeXTcube`.

Nothing here writes. Writing is the risky half and lives on its own, so that
the half which only looks cannot damage anything.
"""

import configparser
import hashlib
import time

#: Where the note about the last write is kept, inside the service's own state
#: directory. It holds one digest and nothing else.
RECEIPT = "written.sha256"

#: What the emulator calls each machine, by the number in the file. The names
#: are Previous's own, from its machine type enumeration.
MACHINE_NAMES = {
    0: "NeXT Computer",
    1: "NeXTcube",
    2: "NeXTstation",
}

#: Which case a machine type comes in. The boot ROM draws the machine on its
#: own panel while it tests the hardware, and it has two pictures: the cube for
#: types 0 and 1, which share an enclosure, and the station for type 2. The
#: interface shows the same two, so this is what decides which.
ENCLOSURES = {
    0: "cube",
    1: "cube",
    2: "station",
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
    parser = _parsed(path)

    system = _section(parser, "System")
    memory = _section(parser, "Memory")
    dimension = _section(parser, "Dimension")

    answer = describe(system, memory, dimension)
    answer["disk"] = _disk(parser)
    return answer


def describe(system, memory, dimension):
    """What a machine is, in words, from the keys that make it.

    @param system - The System keys, as a mapping of name to string. Either a
      section of the file or what machines.settings_for produced, because both
      use the emulator's own key names.
    @param memory - The Memory keys, the same way.
    @param dimension - The Dimension keys, the same way.
    @returns dict describing the machine. No key name from the file appears in
      it: a person choosing a machine should not have to learn that a cube is
      `nMachineType = 1`.

    Written for both sources on purpose. The shelf has to say what a machine
    would be before it is running, and the info window has to say what the
    running one is, and a second copy of this arithmetic would be a second
    answer to the same question.
    """
    machine_type = _int(system, "nMachineType", 1)
    turbo = _bool(system, "bTurbo")
    dimension_seated = _bool(dimension, "bEnabled0")

    return {
        "machine": _machine_name(machine_type, turbo, dimension_seated),
        "enclosure": enclosure(machine_type),
        "cpu": _cpu(system),
        "memory_mb": _memory(memory),
        "banks": [_int(memory, "nMemoryBankSize%d" % bank) for bank in range(4)],
        "screen": _screen(system, dimension_seated),
        "dimension": dimension_seated,
        "turbo": turbo,
        "chips": _chips(system),
    }


def _chips(system):
    """The three chips that decide whether a configuration runs at all.

    @param system - The System keys.
    @returns str, the three named and separated by commas.

    They are here because they are what a machine is made of rather than what
    it does, and because getting one of them wrong produces a machine that
    resets for ever without saying anything.
    """
    clock = "MCCS1850" if _bool(system, "nRTC") else "MC68HC68T1"
    scsi = "NCR53C90A" if _bool(system, "nSCSI") else "NCR53C90"
    bus = "mit NeXTbus" if _bool(system, "bNBIC") else "ohne NeXTbus"
    return "%s, %s, %s" % (clock, scsi, bus)


def note_written(path, state_directory):
    """Records what this service just wrote, so it can be recognised later.

    @param path - The file that was written.
    @param state_directory - pathlib.Path the service may write to, which
      survives a restart.
    @returns bool, False where the note could not be kept. That is not worth an
      exception: the file was written either way, and all that is lost is being
      able to say later who wrote it.

    A digest of the whole file rather than its time, because a time says when
    something happened and this question is whether the file is still the one
    we left behind.
    """
    digest = _digest(path)
    if digest is None:
        return False
    try:
        (state_directory / RECEIPT).write_text(digest)
        return True
    except OSError:
        return False


def _written_by_us(path, state_directory):
    """Whether the file is still the one this service wrote.

    @returns bool. False where there is no note, which is the honest answer:
      this service has written nothing it can recognise.

    Only one side of this is knowable. A file that does not match the note was
    written by somebody else, and Previous's own dialogue and a text editor
    look exactly alike from here.
    """
    if state_directory is None:
        return False
    try:
        noted = (state_directory / RECEIPT).read_text().strip()
    except OSError:
        return False
    return bool(noted) and noted == _digest(path)


def _digest(path):
    """@returns The file's SHA-256 as hex, or None where it cannot be read."""
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def file_state(path, emulator_age_seconds, now=None, state_directory=None):
    """What the file says about itself, held against the machine that runs.

    @param path - pathlib.Path to previous.cfg.
    @param emulator_age_seconds - How long the emulator has been up, or None
      where none is running.
    @param now - The current time, for tests. Defaults to time.time().
    @param state_directory - Where the note from the last write is kept. Left
      out, `written_by_us` answers False.
    @returns dict with `changed_at`, a Unix timestamp or None,
      `newer_than_the_machine`, and `written_by_us`.

    Previous reads this file when it starts and never again, so a file written
    since then holds a machine that nobody has tried. It is not an error and
    not a warning: it is the difference between what runs and what is written
    down, and the only place that difference can be seen.

    With no emulator running the question does not arise, because there is no
    running machine for the file to disagree with.
    """
    changed_at = _changed_at(path)
    started_at = None
    if emulator_age_seconds is not None:
        started_at = (time.time() if now is None else now) - emulator_age_seconds
    return {
        "changed_at": changed_at,
        "newer_than_the_machine": (
            changed_at is not None and started_at is not None
            and changed_at > started_at
        ),
        "written_by_us": _written_by_us(path, state_directory),
    }


def _changed_at(path):
    """@returns When the file was last written, as a Unix timestamp, or None
      where it cannot be read."""
    try:
        return path.stat().st_mtime
    except OSError:
        return None


def enclosure(machine_type):
    """Which case a machine of this type comes in.

    @param machine_type - What the file holds in nMachineType, and what
      machines.py carries as `kind`.
    @returns "cube" or "station". A type nobody knows answers "cube", because
      that is the case NeXT built first and the one an unknown number is most
      likely to be.
    """
    return ENCLOSURES.get(machine_type, "cube")


def matching(path, options):
    """Which of these the file holds exactly.

    @param path - pathlib.Path to previous.cfg.
    @param options - Pairs of (name, settings), as machines.settings_for
      produces them.
    @returns The name of the first whose every setting the file already has,
      or None where the file is none of them.
    @raises NotReadable - The file is not there, or is not INI-shaped.

    A file that is none of them is not broken. It is a machine somebody put
    together, and the difference matters: this tool offers eleven and must not
    present a twelfth as one of those, nor write over it without saying so.

    Asked against the whole list rather than against the machine the file names
    itself after, because two of the eleven differ from another two by their
    clock alone. Previous has no idea of Nitro, so a Nitro configuration calls
    itself by the name of the machine it is a faster version of.
    """
    parser = _parsed(path)
    for name, settings in options:
        if not _differences(parser, settings):
            return name
    return None


def differences(path, settings):
    """Which of these settings the file does not already hold.

    @param path - pathlib.Path to previous.cfg.
    @param settings - Section name to key to value.
    @returns dict of section to dict of key to (what the file has, what was
      wanted). Empty where the file holds all of them.
    @raises NotReadable - The file is not there, or is not INI-shaped.
    """
    return _differences(_parsed(path), settings)


def _differences(parser, settings):
    """@returns The same, from a file already read."""
    found = {}
    for section, keys in settings.items():
        holding = _section(parser, section)
        for key, wanted in keys.items():
            has = holding.get(key)
            if has is None or has.strip() != str(wanted).strip():
                found.setdefault(section, {})[key] = (has, wanted)
    return found


def _parsed(path):
    """@returns The file, read. @raises NotReadable where it cannot be."""
    parser = configparser.ConfigParser()
    parser.optionxform = str          # the file's keys are case sensitive
    try:
        if not parser.read(path):
            raise NotReadable("no such file: %s" % path)
    except configparser.Error as error:
        raise NotReadable(str(error)) from error
    return parser


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
