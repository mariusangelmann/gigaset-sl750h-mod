# Snake on the SL750H PRO (work in progress)

Goal: a playable Snake game on the handset, flashed over USB like everything else
in this kit. No game exists in the stock firmware, so this means injecting CR16C
code into the image and hooking it.

## Hardware facts (from firmware RE + osmocom wiki "Gigaset C430 Hacking")

- SoC: Dialog/Renesas SC14441, CPU = CompactRISC **CR16C+** (24-bit addressing)
- Memory map: RAM at 0x0..0x2000 (app sets sp=0x1fc0, isp=0x2000),
  **flash mapped at 0xF0000** (CPU addr = file offset + 0xF0000),
  peripheral registers at 0xFF0000-0xFFC00 (QSPI controller at 0xFF0C00,
  GPIO ~0xFF4000-0xFF7xxx)
- Display: Sitronix **ST7735** color TFT, driven over QSPI (no SoC framebuffer;
  the app streams pixels)
- Keypad: GPIO matrix on the SoC
- Free space in R1 (main firmware region): ~240 KB of 0xFF at file offset
  **0x1ce29e** (CPU 0x2be29e) — enough for a game
- Toolchain: upstream binutils+gcc support cr16 (`cr16-elf`, `-mcr16c`);
  build script in `build-toolchain.sh`. objdump disassembles R1 with
  `cr16-elf-objdump -D -b binary -m cr16 --adjust-vma=0 r1.bin`

## Plan

1. Write Snake in C (`snake.c`), freestanding, driving the ST7735 over the QSPI
   registers directly and polling the keypad GPIO directly — no dependency on
   the app's UI framework.
2. Place the binary at file 0x1ce29e.
3. Hook: patch the R1 entry (file 0xc06a) to `bal` into the game before normal
   boot; the game exits on a key and returns to the original boot path.
   (Alternative hook: add an AT command to the app's dispatcher.)
4. Recompute CRCs with the 2-byte CRC fixer (crcB(R1) must stay 0xBE12) and
   flash with `sl750h_tool.py flash`.

## Status

- [x] toolchain (binutils cr16-elf-as/objdump working; gcc build script ready)
- [x] memory map + free space located
- [ ] ST7735 init sequence + keypad registers identified in app code
- [ ] snake.c written and compiled
- [ ] hook + flash + live test

Recovery if a bad flash bricks boot: battery out, hold 4+6, reinsert -> emergency
mode -> flash stock image.
