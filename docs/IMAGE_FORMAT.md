# Image format (gunzipped `shark__gqs.bin`, 0x719060 bytes) & CRC model

## Header

- Header block `[0x00:0x58]`: `u16 crc @0` = CRC16-CCITT (poly 0x1021,
  MSB-first, **seed 0x55AA**) over `d[2:0x58]`; `u16 Length @0x02` = 0x58.
- Three 28-byte entries at 0x04 / 0x20 / 0x3C:
  `[u16 type][u32 ofs][u32 len][12B version][u32 flags][u16 crc]`
  - entry@0x04: type 4 (bootloader), R0 = `[0x58 : 0xc05a]`, ver `116.038.00`, crc @0x1E
  - entry@0x20: type 1 (main firmware), R1 = `[0xc05a : 0x3fd05c]`, ver `116.076.02`, crc @0x3A
  - entry@0x3C: type 6 (flashdisk), R2 = `[0x3fd05c : end]`, ver `116.005.00`, crc @0x56
- Each region starts with its own 12-byte version string + 4-byte flags.
  (Version occurrences in a stock image: 0x2A header entry, 0x58 R0, 0xc05a R1,
  0x18299d payload `SHARK_HS` block.)

## Region trailers

- `u16 crcA @end-4` = crc16(0x55AA, region[:-4])
- `u16 crcB @end-2` = crc16(0x55AA, region[:-2])  (crcB covers crcA — write crcA first)
- Header entry crc = crcB of its region (@0x1E, @0x3A), except entry@0x3C uses crcA (@0x56).
- File trailer: last `u16 @end-2` = crc16(0x55AA, **whole file**[:-2]) — a global CRC,
  not a region CRC.

## The one non-obvious rule (why naive patches get `AT^SERR 0` at a region end)

At the end of a region walk the phone checks `crc16(received region data)` against
the **value already on flash** (the old trailer crcB / old header entry crc), not
against the new header you sent in the query phase. So modified content must keep
`crc16(region[:-2])` equal to the on-flash value. Since CRC16 is linear, you can
force any target CRC by tuning 2 free bytes inside the region (e.g. the 0xFF
padding just before the trailer) — solve `crcB(x) == old_crcB` for the 2 bytes `x`
including the crcA bytes they produce (fixed point), then let the tool recompute
crcA/entry CRCs. `fix_all_crcs()` in `sl750h_tool.py` does all of this; for R1 the
2-byte fixer lives at file 0x3FD056 and keeps crcB(R1) == 0xBE12.

## Patch specs (sl750h_tool.py patch)

- `str:0xOFF:"old"=>"new"` — same-length ASCII replacement
- `stru:0xOFF:"old"=>"new"` — same-length UTF-16LE replacement
- `@0xOFF:hexbytes` / `@0xOFF:file.bin` — raw bytes

After patching, all CRCs (crcA/crcB/entry/header/global) are recomputed
automatically. Payload facts: plaintext UI strings around file 0x1b7000-0x1c6000,
source paths `S:\\pform_hs_2015\\...`, JPEGs at ~0x3ff45c+.

## Proven mods (both flashed and booted live)

- mod9: version `116.076.04` + USB string `SL750H-PRO MODDED USB CDC ACM` (`make_mod.py`)
- mod10 hardened: version `116.076.05` + all 18 plaintext HTTP URL hosts in R1
  neutered to DNS-dead names (`make_hardened.py`)
