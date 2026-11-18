// Print addresses of named symbols. Usage: -postScript DumpSyms.java name1,name2
// @category SL750H
import ghidra.app.script.GhidraScript;
import ghidra.program.model.symbol.*;
public class DumpSyms extends GhidraScript {
  public void run() throws Exception {
    for (String n : getScriptArgs()[0].split(",")) {
      SymbolIterator it = currentProgram.getSymbolTable().getSymbols(n.trim());
      if (!it.hasNext()) { println(n+" = (none)"); continue; }
      while (it.hasNext()) { Symbol s=it.next(); println(n+" = "+s.getAddress()); }
    }
  }
}
