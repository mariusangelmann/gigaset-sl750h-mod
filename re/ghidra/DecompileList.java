// Decompile a list of functions (by hex CPU address) to stdout / a file.
// Usage: -postScript DecompileList.java 0x16e95c,0x16e8c6,... [outfile]
// @category SL750H
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import java.io.*;

public class DecompileList extends GhidraScript {
    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        String[] addrs = args[0].split(",");
        PrintWriter out = (args.length > 1)
            ? new PrintWriter(new FileWriter(args[1])) : null;

        DecompInterface d = new DecompInterface();
        d.toggleCCode(true);
        d.openProgram(currentProgram);

        for (String h : addrs) {
            h = h.trim();
            if (h.isEmpty()) continue;
            Address a = currentProgram.getAddressFactory().getDefaultAddressSpace()
                .getAddress(Long.decode(h));
            Function f = getFunctionContaining(a);
            if (f == null) {                     // seed one at this exact address
                new ghidra.app.cmd.disassemble.DisassembleCommand(a, null, true)
                    .applyTo(currentProgram, monitor);
                f = createFunction(a, null);
                if (f == null) f = getFunctionContaining(a);
            }
            String hdr = "\n/* ===== " + h + " "
                + (f != null ? ("(" + f.getName() + " @ " + f.getEntryPoint() + ")") : "(no function)")
                + " ===== */\n";
            emit(out, hdr);
            if (f == null) { emit(out, "// no function at " + h + "\n"); continue; }
            DecompileResults r = d.decompileFunction(f, 60, monitor);
            if (r != null && r.decompileCompleted() && r.getDecompiledFunction() != null)
                emit(out, r.getDecompiledFunction().getC());
            else
                emit(out, "// decompile failed: " + (r != null ? r.getErrorMessage() : "null") + "\n");
        }
        if (out != null) out.close();
    }
    private void emit(PrintWriter out, String s) {
        if (out != null) out.print(s); else print(s);
    }
}
