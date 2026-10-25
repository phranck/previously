// Decompiles the functions that contain the given addresses into one text
// file, each with the places that reference its entry, so a question about
// NeXT code can be read off C rather than off a 68040 listing.
//
//     -postScript Decompile.java <output file> <address>...
//
// An address that no function contains yet becomes the entry of a new one.
//
//@category Previously

import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;

import java.io.PrintWriter;
import java.nio.file.Files;
import java.nio.file.Path;

public class Decompile extends GhidraScript {

    private static final int DECOMPILE_TIMEOUT_SECONDS = 120;

    @Override
    public void run() throws Exception {
        String[] arguments = getScriptArgs();
        DecompInterface decompiler = new DecompInterface();
        decompiler.openProgram(currentProgram);
        try (PrintWriter output = new PrintWriter(Files.newBufferedWriter(Path.of(arguments[0])))) {
            for (int index = 1; index < arguments.length; index++) {
                writeFunction(decompiler, output, arguments[index]);
            }
        } finally {
            decompiler.dispose();
        }
    }

    /** Writes the references to and the decompiled body of the function containing the address. */
    private void writeFunction(DecompInterface decompiler, PrintWriter output, String addressText) throws Exception {
        Address address = toAddr(Long.decode(addressText));
        Function function = getFunctionContaining(address);
        if (function == null && disassemble(address)) {
            function = createFunction(address, null);
        }
        if (function == null) {
            output.println("=== no function at " + addressText);
            return;
        }
        output.println("=== " + function.getName() + " at " + function.getEntryPoint());
        for (Reference reference : getReferencesTo(function.getEntryPoint())) {
            Function caller = getFunctionContaining(reference.getFromAddress());
            output.println("// " + reference.getReferenceType() + " from " + reference.getFromAddress()
                + (caller == null ? "" : " in " + caller.getName()));
        }
        DecompileResults results = decompiler.decompileFunction(function, DECOMPILE_TIMEOUT_SECONDS, monitor);
        if (results.getDecompiledFunction() == null) {
            output.println("// decompiler: " + results.getErrorMessage());
        } else {
            output.println(results.getDecompiledFunction().getC());
        }
    }
}
