# Reverse-engineering notes (SL750H PRO "Shark", Dialog SC1444x / CR16C+)

## Memory & peripherals

- **Address mapping (corrected):** CPU addr = `.upd` file offset + **0xF2FA6**
  = R1 offset + 0xFF000 (R1 = file 0xc05a–0x3fd05c, so R1 offset 0 = CPU 0xFF000).
  The earlier "+0xF0000" rule was wrong: 1595 string references in code resolve
  under +0xF2FA6 against 70 under +0xF0000, and every code-pointer table entry
  lands on a `push …,RA` prologue only under +0xF2FA6.
  Disassemble R1 with `cr16-elf-objdump -D -b binary -m cr16 --adjust-vma=0xff000 r1.bin`.
- Code pointers in tables are stored as **CPU/2** (`jal (rN+1,rN)` doubles them);
  string/data pointers are plain byte addresses.
- Application RAM in use around 0x800000–0x87FFFF (all globals below live there).
- **0xFF0C00 is the flash (QSPI NOR) controller, not the LCD.** Its writers check
  unlock keys 0xdd34/0x92fa; no LCD code touches 0xFF0Cxx.
- GPIO: port p at `0xFF4830 + 0x10*p`, 16-bit regs: DATA +0, SET +2, RESET +4,
  DIR +6, MODE +8 (P0–P5 = 0xFF4830–0xFF4880, P6 0xFF4890, P7 0xFF48A0).
  Code addresses pins logically: `gpio_set(r2=pin, r3=level)` at CPU 0x1DA3E6
  through the 10-byte pin table at CPU 0x2B58DE.
- Watchdog: `storw <reload>, 0xFF4C00` (firmware reloads 0xFE/0xFF inline in
  many hot paths). Timeout is short (well under ~1 s inferred) — any long-running
  loop must kick it.

## Display

- **Sitronix ST7789H2, 240x320, RGB565**, MADCTL 0xC0 (not ST7735 128x160).
  Four panel init tables (“st7789H2-Casil/Yes2/Yes3/Yes”) at CPU 0x2B7A5C,
  0x2B7AD5, 0x2B7B4D, 0x2B7BC5; each table precedes its name string.
  Opcodes: `fa LL CC d…` command+data, `f8` same (+stores last byte),
  `f9 NN` delay, `fb A B` reset pulse, `ff` end. Player at CPU 0x20EC38.
- Bus: SPI block CTRL 0xFF4940 (bit 11 = TX busy), TX 0xFF4942, CTRL1 0xFF4948
  (bit 3 = transfer busy). D/C = logical pin 0x2F (1 = command), CS = logical
  pin 6 (1 = asserted). `spi_cfg(r2=0, r3=clock 1|2, r4=0 8-bit/1 16-bit)` at
  0x1DCE12; synchronous byte/word send loops at 0x1DCE5E / 0x1DCE82.
- `lcd_write` (0x20EB6A) / `lcd_flush` (0x20E7F0) post scheduler task 0 and spin
  until it ran. The scheduler is cooperative (tasks drain only when the current
  one returns, idle marker 0x801837 == 0xFF), so **calling them from inside a UI
  handler deadlocks**. Payloads must drive SPI directly.
- The firmware never sends CASET (columns stay 0–239); it sends RASET+RAMWR per
  row band, with a panel row offset in word 0x8753A0.

## Keypad

- Matrix scanned from the keyboard interrupt (ISR → 0x1D492E → scan state
  machine 0x20F932 → matrix read 0x1D4952), so the raw active-high bitmasks stay
  fresh during a busy loop: **row byte 0x875678, column byte 0x875679**.
  UP r0/c1, DOWN r4/c1, LEFT r1/c0, RIGHT r1/c2, OK r1/c1, red/end (probable)
  r0/c3, `#` r6/c2 (row/column bit numbers). Raw code table at CPU 0x2B7C8C.
- Key-event queue (type,value pairs) at 0x874DEE; consumed by the UI task — do
  not poll it from a payload loop.

## Menus

- Screens are event handlers; event 0x1A = OK/select.
- Main menu: table at CPU 0x2AE8FA (file 0x1BB954), 8 records × 14 bytes:
  +0 visibility predicate (CPU/2 — runs while the menu is built, **not** a select
  handler), +4 sub-item count, +5 u16, +9 RAM availability pointer, +13 index.
  Index 3 = Netzdienste (its predicate 0x16F0BE hard-codes r2=3).
- Main-menu window handler: CPU 0x16FC1E (r7 = event). State struct pointer at
  [0x87546C] (getter 0x16FDB2); **byte +1 = highlighted item index** (the renderer
  0x16E76A multiplies it by 14 into the table). OK handling is item-independent
  (0x16FD82), so a Netzdienste-only hook must test the index itself.
- Hidden "Dev App's" list: dispatcher 0x181B80 (`jal` on 0x2AF691 + idx*8).
  No service code to open it was found in R1.

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
- Free space for payloads: ~240 KB of 0xFF at file 0x1ce29e–0x20a05a (CPU 0x2C1244).

## Snake payload

Built and validated offline; see [snake/README.md](../snake/README.md) and
`make_snake.py`. The previous ST7735/QSPI design was based on the wrong address
mapping and the wrong panel and has been replaced.

## Recovery

Battery out, hold **4+6**, reinsert → emergency mode (red blink) → plug USB →
`python3 sl750h_tool.py flash shark_gqs.upd`. The phone auto-recovered from every
failed flash during development; it never bricked.
