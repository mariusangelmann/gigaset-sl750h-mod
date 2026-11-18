// Prepare an imported SL750H R1 image (CR16C:LE:16:default, base 0xFF000):
// add RAM and I/O blocks, seed functions from an entry list, apply re/symbols.csv.
// Usage (headless -postScript or -preScript): SetupSL750H.java <entries.txt> <symbols.csv>
// @category SL750H
import ghidra.app.script.GhidraScript;
import ghidra.app.cmd.disassemble.DisassembleCommand;
import ghidra.program.model.address.*;
import ghidra.program.model.mem.*;
import ghidra.program.model.symbol.SourceType;
import java.nio.file.*;
import java.util.*;

public class SetupSL750H extends GhidraScript {
    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        Memory mem = currentProgram.getMemory();
        AddressSpace ram = currentProgram.getAddressFactory().getDefaultAddressSpace();
        addBlock(mem, ram, "RAM", 0x800000L, 0x80000L);
        addBlock(mem, ram, "IO", 0xFF0000L, 0x10000L);

        int n = 0;
        for (String line : Files.readAllLines(Paths.get(args[0]))) {
            line = line.trim();
            if (line.isEmpty()) continue;
            Address a = ram.getAddress(Long.parseLong(line, 16));
            if (getFunctionAt(a) != null) continue;
            new DisassembleCommand(a, null, true).applyTo(currentProgram, monitor);
            if (createFunction(a, null) != null) n++;
        }
        println("seeded functions: " + n);

        int s = 0;
        for (String line : Files.readAllLines(Paths.get(args[1]))) {
            if (line.startsWith("#") || line.startsWith("address")) continue;
            String[] f = line.split(",", 5);
            if (f.length < 4) continue;
            Address a = ram.getAddress(Long.decode(f[0]));
            String name = f[2];
            if (f[1].equals("func")) {
                if (getFunctionAt(a) == null) {
                    new DisassembleCommand(a, null, true).applyTo(currentProgram, monitor);
                    createFunction(a, name);
                } else {
                    getFunctionAt(a).setName(name, SourceType.USER_DEFINED);
                }
            } else {
                createLabel(a, name, true, SourceType.USER_DEFINED);
            }
            if (f.length > 4 && !f[4].isEmpty())
                setPlateComment(a, "[" + f[3] + "] " + f[4].replace("\"", ""));
            s++;
        }
        println("applied symbols: " + s);
    }

    private void addBlock(Memory mem, AddressSpace sp, String name, long start, long len) throws Exception {
        Address a = sp.getAddress(start);
        if (mem.getBlock(a) != null) return;
        MemoryBlock b = mem.createUninitializedBlock(name, a, len, false);
        b.setRead(true); b.setWrite(true); b.setExecute(name.equals("RAM"));
        if (name.equals("IO")) b.setVolatile(true);
    }
}
