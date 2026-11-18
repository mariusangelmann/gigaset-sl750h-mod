# AT memory monitor

Adds a live peek/poke to the firmware over the normal USB serial port, so we
can inspect and change the running phone's memory in seconds instead of
reflashing. Built into firmware 116.076.07 by `make_monitor.py` (on top of the
Snake image).

## Use

```
AT^GCTRACER=<hexaddr>            read a 16-bit word    -> replies "0x<VALUE>"
AT^GCTRACER=<hexaddr>,<hexval>   write a 16-bit word   -> OK
AT^GCTRACER=B<hexaddr>,<hexval>  write the low BYTE    -> OK
AT^GCTRACER=C<hexaddr>           CALL code at <hexaddr> -> replies "0x<R0>" 
```

Hex is case-insensitive and a leading `=` is required by the AT syntax.
Addresses are CPU addresses (RAM 0x8xxxxx, I/O 0xFFxxxx, flash 0x0xxxxx).
Malformed input returns ERROR and writes nothing. There is no range guard — it
is a debug tool; a bad write to I/O can hang the phone (recover with 4+6).

On any parse failure the reply is **self-diagnosing**: before `ERROR` it emits
three `0x<WORD>` lines — the argument pointer (high word, then low word) and
the first 16-bit word found there. So a malformed reply still shows where the
monitor looked and what it saw, which is how we pin the real buffer layout on
the handset without guessing.

Examples:
```
AT^GCTRACER=875678      read the keypad row bitmask
AT^GCTRACER=87546C      read the menu-state pointer low word
AT^GCTRACER=FF4C00,00FF kick the watchdog
```

## Run code without flashing

`=B` (byte write) and `=C` (call) let us run new code over USB with no flash:
stage a routine into RAM byte by byte, end it with `jump (ra)` (bytes `EE 0A`),
then call it. `=C<addr>` does `jal`, so it calls the address as-is (the monitor
halves it internally, matching the CPU's `jal (pair)` = jump to pair*2), and
replies with the routine's `r0`. This is how later experiments (a new Snake
hook, a test probe) run instantly; only changes that must survive a reboot get
flashed. The routine runs in the AT task context — same rules as any handler
(don't call lcd_write/lcd_flush, kick the watchdog in long loops).

## How it works

| Piece | Where |
|---|---|
| Payload | file 0x1ce95a = CPU 0x2C1900 (free flash after Snake), 254 bytes |
| Hook | file 0x183324 = ^GCTRACER handler/2 field in AT table record 29 (CPU 0x2762ca): `92 09 08 00` (-> 0x101324) → mon_entry/2 |

`^GCTRACER` was a near-empty debug command. The AT dispatcher `jal`s the
handler (table value x2) with r2 = command index, r3 = syntax byte, r6 = a flag
word.

**Finding the argument.** The first monitor trusted a subagent's report that
the tail pointer arrives in `(r5,r4)`. On the handset that was wrong — every
`=` command returned ERROR — so this version does **not** trust any passed
register. `mon_entry` recomputes the argument pointer the way the firmware's
own dispatcher does, from two globals:

    arg = *(u32*)[0x874887] + (u16)[0x8748a7]

`[0x874887]` points at the received command line and `[0x8748a7]` is the offset
the line parser left just past `=`. `at_begin` (0x101FB4) only clears fields at
`[0x874887]+0x10..+0x18`, so the pointer and offset survive it. The monitor
then parses hex from that pointer, reads or writes the 16-bit word, and emits
its reply with the firmware's own response/OK/ERROR helpers
(`at_send_response_line` 0x10201a, `at_send_ok` 0x1022ee,
`at_send_error` 0x1022f8). (`mon_test`, a second entry point, takes the pointer
directly in `(r5,r4)` so the CR16 sim — which cannot provide the device globals
and mishandles absolute `loadd` — can drive the same body.)

## Build and test

```bash
CR16=<prefix>/bin MON_BASE=0x2c1900 monitor/build.sh         # -> monitor/monitor.bin
CR16=<prefix>/bin python3 monitor/sim/test_monitor.py        # 30 cases in cr16-elf-run
python3 make_monitor.py shark_gqs.upd fw_116.076.07.upd
```

The sim test stubs the response helpers, feeds read/write/malformed tails, and
checks the parser's address/value and read-after-write, mirroring the Snake
tests.

## Why it matters

This is the base for the rest of the RE work: with live memory access we can
confirm variables (such as the real main-menu cursor that the first Snake hook
guessed wrong), watch what changes when a key is pressed, and test a value
before baking it into a flash.
