# AT memory monitor

Adds a live peek/poke to the firmware over the normal USB serial port, so we
can inspect and change the running phone's memory in seconds instead of
reflashing. Built into firmware 116.076.07 by `make_monitor.py` (on top of the
Snake image).

## Use

```
AT^GCTRACER=<hexaddr>            read a 16-bit word   -> replies "0x<VALUE>"
AT^GCTRACER=<hexaddr>,<hexval>   write a 16-bit word  -> OK, no reply line
```

Hex is case-insensitive and a leading `=` is required by the AT syntax.
Addresses are CPU addresses (RAM 0x8xxxxx, I/O 0xFFxxxx, flash 0x0xxxxx).
Malformed input returns ERROR and writes nothing. There is no range guard — it
is a debug tool; a bad write to I/O can hang the phone (recover with 4+6).

Examples:
```
AT^GCTRACER=875678      read the keypad row bitmask
AT^GCTRACER=87546C      read the menu-state pointer low word
AT^GCTRACER=FF4C00,00FF kick the watchdog
```

## How it works

| Piece | Where |
|---|---|
| Payload | file 0x1ce95a = CPU 0x2C1900 (free flash after Snake), 152 bytes |
| Hook | file 0x183324 = ^GCTRACER handler/2 field in AT table record 29 (CPU 0x2762ca): `92 09 08 00` (-> 0x101324) → mon_entry/2 |

`^GCTRACER` was a near-empty debug command. The AT dispatcher `jal`s the
handler (table value x2) with r2 = command index, r3 = syntax byte,
(r5,r4) = pointer to the command-line tail (`=...`), r6 = a flag word. The
monitor parses hex from the tail, reads or writes the 16-bit word, and emits
its reply with the firmware's own response/OK/ERROR helpers
(`at_send_response_line` 0x10201a, `at_send_ok` 0x1022ee,
`at_send_error` 0x1022f8).

## Build and test

```bash
CR16=<prefix>/bin MON_BASE=0x2c1900 monitor/build.sh         # -> monitor/monitor.bin
CR16=<prefix>/bin python3 monitor/sim/test_monitor.py        # 20 cases in cr16-elf-run
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
