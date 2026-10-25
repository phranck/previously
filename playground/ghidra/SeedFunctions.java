// Prepares a raw import of NeXT 68040 code for Ghidra's analysis. A raw image
// has no entry points beyond the one Ghidra is told about, so this seeds a
// function at every link.w a6 prologue, which is how the NeXT compiler opens a
// function. It also adds the zero-filled block that the file leaves out and
// names the symbols that macho68k.py lists, so a kernel import keeps its names.
//
//     -preScript SeedFunctions.java [seed=link] [bss=<start>:<size>] [symbols=<file>]
//
// The symbol file is the output of `macho68k.py symbols <file> .`: one symbol
// per line, as address, section and name.
//
//@category Previously

import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.mem.MemoryBlock;
import ghidra.program.model.symbol.SourceType;

import java.nio.file.Files;
import java.nio.file.Path;

public class SeedFunctions extends GhidraScript {

    /** link.w a6,#<displacement>, the first instruction of a function with a frame. */
    private static final int LINK_A6_OPCODE = 0x4e56;

    /** The section whose symbols are functions; every other symbol is data. */
    private static final String TEXT_SECTION = "__TEXT,__text";

    @Override
    public void run() throws Exception {
        boolean seedLinks = false;
        String zeroFilled = null;
        String symbolFile = null;
        for (String argument : getScriptArgs()) {
            if (argument.equals("seed=link")) {
                seedLinks = true;
            } else if (argument.startsWith("bss=")) {
                zeroFilled = argument.substring("bss=".length());
            } else if (argument.startsWith("symbols=")) {
                symbolFile = argument.substring("symbols=".length());
            } else {
                throw new IllegalArgumentException("unknown argument " + argument);
            }
        }
        if (zeroFilled != null) {
            addZeroFilledBlock(zeroFilled);
        }
        if (seedLinks) {
            seedLinkPrologues();
        }
        if (symbolFile != null) {
            applySymbols(Path.of(symbolFile));
        }
    }

    /**
     * Adds an uninitialized block for memory the program uses but the file
     * does not hold, such as __bss and __common.
     *
     * @param startAndSize start and size as "0x...:0x..."
     */
    private void addZeroFilledBlock(String startAndSize) throws Exception {
        String[] parts = startAndSize.split(":");
        Address start = toAddr(Long.decode(parts[0]));
        long size = Long.decode(parts[1]);
        MemoryBlock block = currentProgram.getMemory().createUninitializedBlock("bss", start, size, false);
        block.setRead(true);
        block.setWrite(true);
    }

    /** Disassembles and creates a function at every even address holding link.w a6. */
    private void seedLinkPrologues() throws Exception {
        int seeded = 0;
        for (MemoryBlock block : currentProgram.getMemory().getBlocks()) {
            if (!block.isInitialized()) {
                continue;
            }
            byte[] bytes = new byte[(int) block.getSize()];
            block.getBytes(block.getStart(), bytes);
            for (int offset = 0; offset + 1 < bytes.length; offset += 2) {
                int word = ((bytes[offset] & 0xff) << 8) | (bytes[offset + 1] & 0xff);
                if (word != LINK_A6_OPCODE) {
                    continue;
                }
                Address address = block.getStart().add(offset);
                if (getFunctionAt(address) == null && disassemble(address) && createFunction(address, null) != null) {
                    seeded++;
                }
            }
        }
        println("seeded " + seeded + " functions at link.w a6 prologues");
    }

    /**
     * Names every symbol of the file: a function for __TEXT,__text, a label
     * for everything else. An existing function at the address is renamed.
     */
    private void applySymbols(Path symbolFile) throws Exception {
        int named = 0;
        for (String line : Files.readAllLines(symbolFile)) {
            String[] fields = line.trim().split("\\s+");
            if (fields.length != 3 || !fields[0].startsWith("0x")) {
                continue;
            }
            Address address = toAddr(Long.decode(fields[0]));
            String name = fields[2];
            if (fields[1].equals(TEXT_SECTION)) {
                disassemble(address);
                Function function = getFunctionAt(address);
                if (function == null) {
                    function = createFunction(address, name);
                } else {
                    function.setName(name, SourceType.IMPORTED);
                }
                if (function == null) {
                    createLabel(address, name, true);
                }
            } else {
                createLabel(address, name, true);
            }
            named++;
        }
        println("named " + named + " symbols");
    }
}
