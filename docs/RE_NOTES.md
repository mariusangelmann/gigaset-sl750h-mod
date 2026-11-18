# Reverse-engineering notes (SL750H PRO "Shark", Dialog SC1444x / CR16C+)

## Memory & peripherals

- Flash CPU base **0xF0000**: CPU addr = file offset + 0xF0000.
- RAM 0x0–0x2000 (app sets sp=0x1fc0, isp=0x2000). Peripherals 0xFF0000–0xFFC00.
- QSPI controller (display + external flash):
  CTRL 0xFF0C00 (32-bit; bit0 SIO, bit1 DIO, bit2 QIO, bit3 ENABLE_BUS,
  bit4 DISABLE_BUS), CFG 0xFF0C04, RECV 0xFF0C08, STATUS 0xFF0C14 (bit0 = BUSY),
  TX8/16/32 0xFF0C18, RX8/16/32 0xFF0C1C. **LCD CS is controller-managed**
  (CTRL bus bits), not a GPIO. Flash driver in R1 at CPU 0x3b0660–0x3b06fa
  (init 0x3b0660, cfg 0x3b0686, write 0x3b06a4, read 0x3b06ce).
- GPIO: port p at `0xFF4830 + 0x10*p`, 16-bit regs: DATA +0, SET +2, RESET +4,
  DIR +6, MODE +8. P0=0xFF4830 … P5=0xFF4880.
- Display: Sitronix **ST7735**, 128x160, over QSPI (no SoC framebuffer).

## CR16C toolchain (asm path works; GCC port is gone/broken)

- binutils 2.44 `cr16-elf-as/ld/objdump/objcopy` work (see `snake/build-toolchain.sh`).
  GCC's cr16 port was removed in GCC 13 and is broken in ≤12 — write asm.
- gas traps: no `~` in expressions (use explicit masks), no 5-reg `push`,
  `(sym):l` illegal (use `sym:l`), `-m` flag ambiguous (plain `cr16-elf-as` fine).
- **Encoding gotcha:** `loadw 0xFF0C14:m` with a *literal* encodes the 20-bit
  sign-extended absolute form (0xFF page, opcode 0x0f family = 0xFF0000|disp);
  with a *symbol* gas silently picks the 16-bit form. Use literals for 0xFFxxxx.

## Firmware content map (R1)

- AT command names at file ~0x182c41: +CGMI/CGMM/CGMR/CGSN/CBC/CSQ/CMEE,
  ^SRSR/^SSWU/^SERR/^SSWR/^SSWS/^SGBD (flash), ^SQWE (OBEX), ^SGST, ^SURL,
  ^SACO, ^SHSN, ^HSMM, ^HMWI, ^GCBL, ^GCTRACER, ^GCUSBETHERNET, ^GCSCALL,
  ^GCSRESULT, ^WPPN/^WPCS/^WPPS, plus a `/usr/share/scripts/%s &` string
  (script-exec feature — treat flashdisk content as untrusted).
- Plaintext UI strings around file 0x1b7000–0x1c6000, incl. a hidden test menu
  ("Approval Test", "LDS Testcases", "SUOTA w/o CISS", "Url 1 Patch", …) —
  candidate hook for launching a payload from the on-device menu.
- High-entropy blobs scattered through R1 (0x18a05a–0x1ab05a etc.) are
  images/sounds, not one compressed code region.
- Free space for payloads: ~240 KB of 0xFF at file ~0x1ce29e (CPU 0x2be29e).

## Snake payload (WIP)

Goal: run Snake on the 128x160 LCD, injected at CPU 0x2be29e, launched from the
on-device menu (repoint a hidden test-menu entry's handler) or via an AT command.
`snake/snake.s` assembles to 508 bytes with the entry trampoline first
(`snake_entry` at 0x2be29e → `bal snake_main` → `jump (ra)` on exit).
**Not yet flashed** — LCD RS/RST GPIO bits and keypad matrix pins still need to be
confirmed from the app code (the QSPI driver's callers sit in data regions).

## Recovery

Battery out, hold **4+6**, reinsert → emergency mode (red blink) → plug USB →
`python3 sl750h_tool.py flash shark_gqs.upd`. The phone auto-recovered from every
failed flash during development; it never bricked.
