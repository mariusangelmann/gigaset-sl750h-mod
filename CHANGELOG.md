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

## 116.076.07 — AT memory monitor (`make_monitor.py`)

Everything from 116.076.06, plus:

| Offset | Bytes | Change |
|---|---|---|
| 0x1ce95a | 216 (was 0xFF) | AT monitor payload (read/write/byte-write/call) (`monitor/monitor.s`) |
| 0x183324 | `92090800` -> `800c1600` | `^GCTRACER` handler/2 -> monitor (CPU 0x2762ca) |
| 0x3fd056 | 2 | CRC fixer re-solved; crcB(R1) stays 0xBE12 |
| 0x2a, 0xc05a, 0x18299d | 10 | Version -> 116.076.07 |

Adds `AT^GCTRACER=<addr>` (read word) and `AT^GCTRACER=<addr>,<val>` (write
word) over USB. Verified offline (20 sim cases, patch bytes, CRCs). Not yet flashed.
