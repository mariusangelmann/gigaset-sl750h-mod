# Reverse-engineering setup

Reusable RE environment for the SL750H PRO R1 firmware region, plus a growing
symbol ledger. Addresses are real CPU addresses (file offset + 0xF2FA6; R1
offset 0 = CPU 0xFF000).

## symbols.csv — the single source of truth

One row per known address: `address,kind,name,status,note`.

- `kind`: `func`, `data`, `ram`, `io`.
- `status`: `verified` (checked against disassembly/bytes, or on device) or
  `hypothesis` (plausible, unproven). **Never promote a hypothesis to verified
  without evidence** — wrong "verified" facts are what sent the first Snake
  hook to the wrong handler.

Everything downstream (Ghidra import, the ELF symbols) is generated from this
file, so naming a function once names it everywhere.

## Ghidra (decompiler)

Ghidra 12.1.x ships a CR16C processor module. On macOS the decompiler native
must be built once (`support/gradle/gradlew buildNatives`, needs a JDK and
Xcode). Then import R1 headless and apply our symbols:

```bash
export GHIDRA_INSTALL_DIR=<ghidra> JAVA_HOME=<jdk21>
"$GHIDRA_INSTALL_DIR/support/analyzeHeadless" <proj_dir> sl750h \
  -import r1.bin -processor CR16C:LE:16:default \
  -loader BinaryLoader -loader-baseAddr 0xff000 \
  -scriptPath re/ghidra -preScript SetupSL750H.java re/entries.txt re/symbols.csv
```

`entries.txt` is the list of function entry points (addresses that are both a
`bal` target and a `push …,RA` prologue), extracted from the disassembly.
`SetupSL750H.java` adds the RAM (0x800000) and I/O (0xFF0000) blocks, seeds
those functions, and applies the names and comments from `symbols.csv`.

## REA (morluto/rea)

REA drives disassemblers/decompilers for agents. Its Ghidra provider needs an
ELF, so wrap R1 as a CR16 ELF at the right base (bytes identical to r1.bin):

```bash
cr16-elf-objcopy -I binary -O elf32-cr16 -B cr16 \
  --rename-section .data=.text,alloc,load,readonly,code,contents r1.bin r1raw.o
cr16-elf-ld -T re/r1.ld r1raw.o -o sl750h_r1.elf   # r1.ld also pulls in symbols.csv names
```

`rea inspect-with-objdump <elf> disassemble` works with a `cr16-elf-objdump`
early on `PATH`. (Ghidra-provider decompile of this ELF is still being wired
up; the headless import above is the working decompiler path meanwhile.)

## AT command surface (for the on-device monitor)

The AT command table is at CPU 0x2761b6: 10-byte records
`{u32 name_ptr, u32 handler/2, u16 flags}`. Dispatch `jal`s `handler*2` at
0x1024dc with the subtype in r2 and the argument pointer in (r5,r4). Response
helpers: `at_send_response_line` 0x10201a, `at_send_ok` 0x1022ee,
`at_send_error` 0x1022f8. `^GCTRACER` (0x101324) is a near-empty debug command
and the planned host for a peek/poke/call monitor.
