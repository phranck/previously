#!/usr/bin/env python3
"""Reads a NeXT-era Mach-O file for the 68040 and says where things are.

NeXTSTEP 3.3 ships its kernel and its WindowServer as 32-bit big-endian
Mach-O files with a symbol table, because loadable kernel servers link
against the kernel by name. That symbol table is what makes a search for the
screen geometry tractable: a hit on a constant is worth little on its own, and
a hit three words into a named data symbol is a lead.

The reader answers four questions on the command line:

    macho68k.py info <file>                 segments, sections, symbol count
    macho68k.py symbols <file> [regex]      defined symbols, optionally filtered
    macho68k.py find <file> <value>...      every place the values occur, as
                                            16 and 32 bit big-endian words,
                                            with the nearest symbol
    macho68k.py near <file> <width> <height> [window]
                                            places where both values occur
                                            within one window of bytes, which
                                            is how a geometry record looks
    macho68k.py dump <file> <symbol|0xaddr> [length]
                                            a hex dump at a symbol or address

Only the standard library is used, so the script runs wherever Python 3 is.
"""

import argparse
import bisect
import re
import struct
import sys

MACH_O_MAGIC_BIG_ENDIAN = b"\xfe\xed\xfa\xce"
MACH_HEADER_SIZE = 28
LOAD_COMMAND_SEGMENT = 1
LOAD_COMMAND_SYMTAB = 2
SEGMENT_COMMAND_SIZE = 56
SECTION_SIZE = 68
NLIST_SIZE = 12
SYMBOL_TYPE_MASK = 0x0E
SYMBOL_TYPE_SECTION = 0x0E
SYMBOL_STAB_MASK = 0xE0
DEFAULT_WINDOW_BYTES = 64
DEFAULT_DUMP_LENGTH = 96
CPU_TYPE_NAMES = {6: "m68k", 7: "i386", 18: "powerpc", 11: "hppa", 14: "sparc"}
FILE_TYPE_NAMES = {1: "object", 2: "execute", 5: "preload", 6: "dylib"}


class Section:
    """One section of a segment, with where it sits in memory and in the file."""

    def __init__(self, name, address, size, file_offset):
        self.name = name
        self.address = address
        self.size = size
        self.file_offset = file_offset

    def holds_address(self, address):
        """@returns bool - Whether the address falls inside this section."""
        return self.address <= address < self.address + self.size


class Segment:
    """One LC_SEGMENT load command and the sections it carries."""

    def __init__(self, name, vm_address, vm_size, file_offset, file_size, sections):
        self.name = name
        self.vm_address = vm_address
        self.vm_size = vm_size
        self.file_offset = file_offset
        self.file_size = file_size
        self.sections = sections

    def holds_file_offset(self, file_offset):
        """@returns bool - Whether the file offset lies in this segment's file bytes."""
        return self.file_offset <= file_offset < self.file_offset + self.file_size

    def holds_address(self, address):
        """@returns bool - Whether the address lies in this segment's memory range."""
        return self.vm_address <= address < self.vm_address + self.vm_size


class Symbol:
    """One entry of the symbol table that names an address in a section.

    Debugging stabs and undefined symbols are left out when the table is read,
    because neither names a place in the file.
    """

    def __init__(self, name, address, section_number):
        self.name = name
        self.address = address
        self.section_number = section_number


class MachO:
    """A parsed 32-bit big-endian Mach-O file.

    @param data - The whole file as bytes.
    """

    def __init__(self, data):
        if data[:4] != MACH_O_MAGIC_BIG_ENDIAN:
            raise SystemExit("not a 32-bit big-endian Mach-O file: magic %s" % data[:4].hex())
        self.data = data
        (_magic, self.cpu_type, self.cpu_subtype, self.file_type,
         command_count, _commands_size, self.flags) = struct.unpack(">7I", data[:MACH_HEADER_SIZE])
        self.segments = []
        self.symbol_table_command = None
        offset = MACH_HEADER_SIZE
        for _command_index in range(command_count):
            command, command_size = struct.unpack(">II", data[offset:offset + 8])
            if command == LOAD_COMMAND_SEGMENT:
                self.segments.append(self._read_segment(offset))
            elif command == LOAD_COMMAND_SYMTAB:
                self.symbol_table_command = struct.unpack(">4I", data[offset + 8:offset + 24])
            offset += command_size
        self.symbols = self._read_symbols()
        self._symbol_addresses = [symbol.address for symbol in self.symbols]

    def _read_segment(self, offset):
        """Reads one segment command and its sections at the given file offset."""
        name = self.data[offset + 8:offset + 24].rstrip(b"\0").decode("ascii", "replace")
        (vm_address, vm_size, file_offset, file_size, _max_protection,
         _initial_protection, section_count, _flags) = struct.unpack(">8I", self.data[offset + 24:offset + SEGMENT_COMMAND_SIZE])
        sections = []
        section_offset = offset + SEGMENT_COMMAND_SIZE
        for _section_index in range(section_count):
            section_name = self.data[section_offset:section_offset + 16].rstrip(b"\0").decode("ascii", "replace")
            segment_name = self.data[section_offset + 16:section_offset + 32].rstrip(b"\0").decode("ascii", "replace")
            address, size, section_file_offset = struct.unpack(">3I", self.data[section_offset + 32:section_offset + 44])
            sections.append(Section("%s,%s" % (segment_name, section_name), address, size, section_file_offset))
            section_offset += SECTION_SIZE
        return Segment(name, vm_address, vm_size, file_offset, file_size, sections)

    def _read_symbols(self):
        """Reads the defined, non-debugging symbols, sorted by address."""
        if self.symbol_table_command is None:
            return []
        symbol_offset, symbol_count, string_offset, _string_size = self.symbol_table_command
        symbols = []
        for symbol_index in range(symbol_count):
            entry_offset = symbol_offset + NLIST_SIZE * symbol_index
            string_index, symbol_type, section_number, _description, value = struct.unpack(
                ">iBBhI", self.data[entry_offset:entry_offset + NLIST_SIZE])
            if symbol_type & SYMBOL_STAB_MASK:
                continue
            if symbol_type & SYMBOL_TYPE_MASK != SYMBOL_TYPE_SECTION:
                continue
            name = self._string_at(string_offset + string_index) if string_index > 0 else ""
            symbols.append(Symbol(name, value, section_number))
        symbols.sort(key=lambda symbol: symbol.address)
        return symbols

    def _string_at(self, offset):
        """@returns str - The NUL-terminated string at a file offset."""
        end = self.data.index(b"\0", offset)
        return self.data[offset:end].decode("ascii", "replace")

    def address_of_file_offset(self, file_offset):
        """@returns int or None - The memory address the file offset is loaded at."""
        for segment in self.segments:
            if segment.holds_file_offset(file_offset):
                return segment.vm_address + (file_offset - segment.file_offset)
        return None

    def file_offset_of_address(self, address):
        """@returns int or None - The file offset holding the bytes for an address."""
        for segment in self.segments:
            if segment.holds_address(address) and segment.file_size:
                relative = address - segment.vm_address
                if relative < segment.file_size:
                    return segment.file_offset + relative
        return None

    def section_of_address(self, address):
        """@returns Section or None - The section the address falls in."""
        for segment in self.segments:
            for section in segment.sections:
                if section.holds_address(address):
                    return section
        return None

    def nearest_symbol(self, address):
        """@returns (Symbol, int) or (None, None) - The last symbol at or before the address and the distance to it."""
        position = bisect.bisect_right(self._symbol_addresses, address)
        if position == 0:
            return None, None
        symbol = self.symbols[position - 1]
        return symbol, address - symbol.address

    def symbol_named(self, name):
        """@returns Symbol or None - The symbol with exactly this name, trying a leading underscore as well."""
        for candidate in self.symbols:
            if candidate.name == name or candidate.name == "_" + name:
                return candidate
        return None

    def describe_file_offset(self, file_offset):
        """@returns str - Address, section and nearest symbol for a file offset, in one line."""
        address = self.address_of_file_offset(file_offset)
        if address is None:
            return "file 0x%06x (outside every segment)" % file_offset
        section = self.section_of_address(address)
        symbol, distance = self.nearest_symbol(address)
        section_name = section.name if section else "?"
        symbol_text = "%s+0x%x" % (symbol.name, distance) if symbol else "no symbol"
        return "file 0x%06x addr 0x%08x %-22s %s" % (file_offset, address, section_name, symbol_text)


def load(path):
    """@returns MachO - The parsed file at the path."""
    with open(path, "rb") as handle:
        return MachO(handle.read())


def encodings_of(value):
    """@returns list of (bytes, str) - The 32 and 16 bit big-endian encodings of a value."""
    encodings = [(struct.pack(">I", value), "u32")]
    if value < 0x10000:
        encodings.append((struct.pack(">H", value), "u16"))
    return encodings


def find_all(data, needle):
    """@returns list of int - Every file offset where the needle occurs, aligned to two bytes.

    The 68040 keeps its words on even addresses, so an odd hit is a coincidence
    inside other data and is not reported.
    """
    offsets = []
    position = data.find(needle)
    while position != -1:
        if position % 2 == 0:
            offsets.append(position)
        position = data.find(needle, position + 1)
    return offsets


def command_info(macho, _arguments):
    """Prints the header, the segments with their sections, and the symbol count."""
    print("cpu %s  type %s  segments %d  symbols %d" % (
        CPU_TYPE_NAMES.get(macho.cpu_type, macho.cpu_type), FILE_TYPE_NAMES.get(macho.file_type, macho.file_type),
        len(macho.segments), len(macho.symbols)))
    for segment in macho.segments:
        print("%-16s addr 0x%08x size 0x%08x file 0x%08x+0x%08x" % (
            segment.name, segment.vm_address, segment.vm_size, segment.file_offset, segment.file_size))
        for section in segment.sections:
            print("    %-28s addr 0x%08x size 0x%08x file 0x%08x" % (
                section.name, section.address, section.size, section.file_offset))


def command_symbols(macho, arguments):
    """Prints the defined symbols, filtered by a regular expression when one is given."""
    pattern = re.compile(arguments.pattern) if arguments.pattern else None
    for symbol in macho.symbols:
        if pattern and not pattern.search(symbol.name):
            continue
        section = macho.section_of_address(symbol.address)
        print("0x%08x %-22s %s" % (symbol.address, section.name if section else "?", symbol.name))


def command_find(macho, arguments):
    """Prints every aligned occurrence of each value, as 32 and as 16 bit word."""
    for value in arguments.values:
        for needle, width in encodings_of(value):
            offsets = find_all(macho.data, needle)
            print("== %d as %s: %d hits" % (value, width, len(offsets)))
            for offset in offsets[:arguments.limit]:
                print("   " + macho.describe_file_offset(offset))
            if len(offsets) > arguments.limit:
                print("   ... %d more" % (len(offsets) - arguments.limit))


def command_near(macho, arguments):
    """Prints places where the width and the height both occur within one window.

    A screen geometry record keeps its width and height a few bytes apart, so
    two hits inside one window are the shape to look for, and a hit on either
    value alone is noise.
    """
    width_offsets = set()
    for needle, _width in encodings_of(arguments.width):
        width_offsets.update(find_all(macho.data, needle))
    for needle, _width in encodings_of(arguments.height):
        for height_offset in find_all(macho.data, needle):
            close = sorted(offset for offset in width_offsets if abs(offset - height_offset) <= arguments.window)
            if not close:
                continue
            first = min(close[0], height_offset)
            print(macho.describe_file_offset(first))
            print("    width at +%d, height at +%d" % (close[0] - first, height_offset - first))
            print("    " + macho.data[first:first + arguments.window].hex(" ", 4))


def command_dump(macho, arguments):
    """Prints a hex dump starting at a symbol or an address."""
    if arguments.where.startswith("0x"):
        address = int(arguments.where, 16)
    else:
        symbol = macho.symbol_named(arguments.where)
        if symbol is None:
            raise SystemExit("no symbol named %s" % arguments.where)
        address = symbol.address
    file_offset = macho.file_offset_of_address(address)
    if file_offset is None:
        raise SystemExit("address 0x%08x has no bytes in the file" % address)
    print(macho.describe_file_offset(file_offset))
    for row_start in range(0, arguments.length, 16):
        row = macho.data[file_offset + row_start:file_offset + row_start + 16]
        words = " ".join(row[position:position + 4].hex() for position in range(0, len(row), 4))
        printable = "".join(chr(byte) if 32 <= byte < 127 else "." for byte in row)
        print("0x%08x  %-36s %s" % (address + row_start, words, printable))


def resolve(macho, where):
    """@returns int - The address a symbol name or a 0x address stands for."""
    if where.startswith("0x"):
        return int(where, 16)
    base, _plus, offset_text = where.partition("+")
    symbol = macho.symbol_named(base)
    if symbol is None:
        raise SystemExit("no symbol named %s" % base)
    return symbol.address + (int(offset_text, 0) if offset_text else 0)


def command_at(macho, arguments):
    """Prints the section and the nearest symbol for an address, also for one without file bytes."""
    address = resolve(macho, arguments.where)
    section = macho.section_of_address(address)
    symbol, distance = macho.nearest_symbol(address)
    print("addr 0x%08x %-22s %s" % (address, section.name if section else "?",
                                     "%s+0x%x" % (symbol.name, distance) if symbol else "no symbol"))


def command_disasm(macho, arguments):
    """Prints a 68040 disassembly from a symbol or address, with symbol names on branch targets and absolute addresses.

    Capstone does the decoding, so it has to be importable; the playground's
    virtualenv has it.
    """
    try:
        import capstone
    except ImportError:
        raise SystemExit("capstone is not importable; run with the playground virtualenv's python")
    address = resolve(macho, arguments.where)
    file_offset = macho.file_offset_of_address(address)
    if file_offset is None:
        raise SystemExit("address 0x%08x has no bytes in the file" % address)
    code = macho.data[file_offset:file_offset + arguments.length]
    decoder = capstone.Cs(capstone.CS_ARCH_M68K, capstone.CS_MODE_M68K_040)
    for instruction in decoder.disasm(code, address):
        symbol, distance = macho.nearest_symbol(instruction.address)
        label = ""
        if symbol and distance == 0:
            label = "%s:\n" % symbol.name
        operands = instruction.op_str
        for match in re.finditer(r"\$([0-9a-f]{6,8})", operands):
            target = int(match.group(1), 16)
            target_symbol, target_distance = macho.nearest_symbol(target)
            if target_symbol and target_distance < 0x10000:
                operands = operands.replace(match.group(0), "%s<%s+0x%x>" % (match.group(0), target_symbol.name, target_distance), 1)
        print("%s0x%08x  %-24s %s %s" % (label, instruction.address, instruction.bytes.hex(), instruction.mnemonic, operands))


def main():
    """Parses the command line and runs the chosen command."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    subparsers = parser.add_subparsers(dest="command", required=True)

    at_parser = subparsers.add_parser("at")
    at_parser.add_argument("file")
    at_parser.add_argument("where")
    at_parser.set_defaults(run=command_at)

    disasm_parser = subparsers.add_parser("disasm")
    disasm_parser.add_argument("file")
    disasm_parser.add_argument("where")
    disasm_parser.add_argument("length", nargs="?", type=lambda text: int(text, 0), default=DEFAULT_DUMP_LENGTH)
    disasm_parser.set_defaults(run=command_disasm)

    info_parser = subparsers.add_parser("info")
    info_parser.add_argument("file")
    info_parser.set_defaults(run=command_info)

    symbols_parser = subparsers.add_parser("symbols")
    symbols_parser.add_argument("file")
    symbols_parser.add_argument("pattern", nargs="?")
    symbols_parser.set_defaults(run=command_symbols)

    find_parser = subparsers.add_parser("find")
    find_parser.add_argument("file")
    find_parser.add_argument("values", nargs="+", type=lambda text: int(text, 0))
    find_parser.add_argument("--limit", type=int, default=40)
    find_parser.set_defaults(run=command_find)

    near_parser = subparsers.add_parser("near")
    near_parser.add_argument("file")
    near_parser.add_argument("width", type=lambda text: int(text, 0))
    near_parser.add_argument("height", type=lambda text: int(text, 0))
    near_parser.add_argument("window", nargs="?", type=int, default=DEFAULT_WINDOW_BYTES)
    near_parser.set_defaults(run=command_near)

    dump_parser = subparsers.add_parser("dump")
    dump_parser.add_argument("file")
    dump_parser.add_argument("where")
    dump_parser.add_argument("length", nargs="?", type=int, default=DEFAULT_DUMP_LENGTH)
    dump_parser.set_defaults(run=command_dump)

    arguments = parser.parse_args()
    arguments.run(load(arguments.file), arguments)


if __name__ == "__main__":
    main()
