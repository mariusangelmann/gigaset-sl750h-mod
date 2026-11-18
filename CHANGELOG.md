# Firmware image changelog

All offsets are `.upd` file offsets (CPU = offset + 0xF2FA6). Every image is
built from the stock `116.076.02` image by a script in this repo; every
change below is a same-length overwrite followed by a CRC recomputation.

## 116.076.06 — Snake (`make_snake.py`)

Everything from 116.076.05, plus:

| Offset | Bytes | Change |
|---|---|---|
| 0x1ce29e | 1716 (was 0xFF) | Snake payload + menu hook trampoline (`snake/snake.s`) |
| 0x7cca2 | `b7521a000018` → `1000e105fc15` | Main-menu OK compare → `br 0x2C1244` |
| 0x3fd056 | 2 | CRC fixer re-solved; crcB(R1) stays 0xBE12 |
| 0x2a, 0xc05a, 0x18299d | 10 | Version → 116.076.06 |
| CRC fields | – | R1 crcA, header CRC, file CRC recomputed |

Verified offline: the only bytes that differ from 116.076.05 are the ones
above; all CRCs are consistent. Not yet flashed.

## 116.076.05 — Hardened (`make_hardened.py`)

Version bump, USB product string `SL750H-PRO MODDED USB CDC ACM`, every
plaintext `http://` host in R1 neutered (see `docs/SECURITY_HARDENING.md`),
CRC fixer. `make_hardened.py` reproduces the image on the phone byte for byte
(sha256 `90fa5b9c…`).

## 116.076.04 — Mod (`make_mod.py`)

Version bump and USB string.

## Backups

Stock recovery image `SL750H_116.076.02_stock_recovery.upd`
(sha256 `71193f9a…7e44c52`) and the .04/.05 builds are kept outside the repo.
`.upd` files are not committed.

## 116.076.09 — AT monitor on the correct command (`make_monitor.py`)

Everything from 116.076.06, plus the monitor payload, now hooked onto the
**right** AT command with the `=` syntax opened:

| Offset | Bytes | Change |
|---|---|---|
| 0x1ce95a | 254 (was 0xFF) | AT monitor payload (`monitor/monitor.s`) |
| 0x18331a | `77090800` -> `800c1600` | **^GCTRACER** (rec 28) handler/2 -> monitor (CPU 0x2762c0) |
| 0x183323 | `21` -> `31` | ^GCTRACER flags high byte: add `0x10` so `=` (set) reaches the handler |
| 0x3fd056 | 2 | CRC fixer re-solved (`0x0090`); crcB(R1) stays 0xBE12 |
| 0x2a, 0xc05a, 0x18299d | 10 | Version -> 116.076.09 |

**Why .07/.08 did nothing on the handset.** The AT table record is
`{u32 handler/2, u32 name_ptr, u16 flags}` (stride 10, base CPU 0x2761a8). The
.07/.08 builds used a wrong field order and repointed record **29**
(`^GCUSBETHERN`), not `^GCTRACER` (record 28) — so `AT^GCTRACER` always ran its
original handler and our code never executed. Separately, the dispatcher gates
syntax before calling any handler: `(flags_high_byte & received_syntax) == 0 ->
ERROR`, with `=` = 0x10 and execute = 0x20. `^GCTRACER`'s stock high byte 0x21
allows only execute, so every `=` form returned ERROR regardless. .09 hooks
record 28 and sets its high byte to 0x31. The mask decode was confirmed live
(`AT+CMEE=2`, high byte 0xff, returns OK). Verified offline (30 sim cases,
patch bytes incl. rec29 left stock, CRCs).

**Flashed and confirmed on hardware.** `AT^GCTRACER=2C1900` → `0x1C7` (our own
payload's first word), `=875678` → `0x0` (keypad row bitmask, no key),
`=9100,1234` then `=9100` → `0x1234`, byte-write verified (`=B9100,FF` →
`0x12FF`). One quirk: the firmware re-dispatches the `=` handler in a loop until
the port is closed, so use `monitor/mon.py` (one command per port open), which
reads the first reply and closes to halt the loop. The value is always correct;
a clean "mark the line consumed" fix can ride the next flash.

## 116.076.07 — AT memory monitor (`make_monitor.py`)

Everything from 116.076.06, plus:

| Offset | Bytes | Change |
|---|---|---|
| 0x1ce95a | 254 (was 0xFF) | AT monitor payload (read/write/byte-write/call) (`monitor/monitor.s`) |
| 0x183324 | `92090800` -> `800c1600` | `^GCTRACER` handler/2 -> monitor (CPU 0x2762ca) |
| 0x3fd056 | 2 | CRC fixer re-solved (`0x009f`); crcB(R1) stays 0xBE12 |
| 0x2a, 0xc05a, 0x18299d | 10 | Version -> 116.076.07 |

Adds `AT^GCTRACER=<addr>` (read word), `=<addr>,<val>` (write word),
`=B<addr>,<val>` (byte write), and `=C<addr>` (call) over USB.

**Correction (2026-11-18):** the first .07 build flashed to the handset
returned ERROR for every `=` command. Cause: it read the argument pointer from
register `(r5,r4)` on a subagent's report, but that register does not point at
the argument on the device. The payload now recomputes the pointer from the
firmware globals `*(u32*)[0x874887] + (u16)[0x8748a7]` (as the AT dispatcher
does), and on any parse failure emits three diagnostic `0x<WORD>` lines (arg
pointer high, low, first word there) before ERROR, so a device failure is
self-explaining. Payload grew 216 -> 254 bytes. Verified offline (30 sim cases,
patch bytes, CRCs consistent). This corrected .07 supersedes the earlier .07
build; not yet reflashed.
