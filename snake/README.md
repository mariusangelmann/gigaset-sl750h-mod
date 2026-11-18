# Snake on the SL750H PRO

Selecting **Netzdienste** in the main menu (OK) starts Snake. Built by
`make_snake.py` on top of the hardened image, as firmware **116.076.06**.

Status: built and verified offline (game logic in the CR16 simulator, patch
bytes and CRCs checked). **Not yet tested on the handset.**

## Controls

- Arrow keys steer (reversing into yourself is ignored).
- Red/end key or `#` quits back to the menu.
- After a collision the border flashes magenta: OK restarts, red/`#` quits.
- Yellow pips in the top bar count the food eaten; speed rises with each one
  until 18.

## How it works

| Piece | Where | What |
|---|---|---|
| Payload | file 0x1ce29e = CPU 0x2C1244 (erased 0xFF area in R1) | `snake.bin`, 1716 bytes: hook trampoline, then the game |
| Hook | file 0x7cca2 = CPU 0x16fc48 | `b7 52 1a 00 00 18` (`cmpw $0x1a,r7; beq 0x16fd82`) → `10 00 e1 05 fc 15` (`br 0x2c1244`); the next 2 bytes (`36 01`) are now dead |
| CRC fixer | file 0x3fd056 | keeps crc16(R1[:-2]) = 0xBE12, the value already on flash |

The hook sits in the main-menu window handler (0x16fc1e). Its first compares
(events 0, 4, 5, 0xa, 0xe, 0x12) run as before; the compare for OK (0x1a) now
branches to the trampoline, which:

1. redoes `cmpw $0x1a,r7` and, for any other event, resumes the original
   compare chain at 0x16fc50;
2. on OK reads the highlighted item from `[0x87546c]+1` and, if it is 3
   (Netzdienste), calls the game;
3. then continues into the original OK handling at 0x16fd82, so the UI
   carries on and repaints itself.

The game runs as a blocking loop inside the handler and therefore:

- drives the ST7789 over SPI itself (CS pin 6, D/C pin 0x2F, `spi_cfg`
  0x1DCE12, TX register 0xFF4942). It never calls `lcd_write`/`lcd_flush`,
  which would deadlock (see docs/RE_NOTES.md, Display);
- kicks the watchdog (`0xFF → 0xFF4C00`) in every loop;
- polls the ISR-refreshed key bitmasks at 0x875678/0x875679;
- on exit clears the screen, restores the full 240×320 window and 16-bit SPI
  mode, releases CS, and returns 1.

Playfield: 15×19 cells of 16 px below a 16 px score bar. All game state lives
in a 260-byte stack frame; nothing in firmware RAM is written.

## Build and test

```bash
CR16=<prefix>/bin snake/build.sh                       # -> snake/snake.bin
CR16=<prefix>/bin python3 snake/sim/test_snake.py      # 8 scenarios in cr16-elf-run
python3 make_snake.py shark_gqs.upd snake_116.076.06.upd
```

`build-toolchain.sh` builds binutils. The simulator is `sim/cr16` from
gdb-15.2: configure with `--target=cr16-elf --disable-gdb`, then
`make MAKEINFO=true all-sim install-sim`.
`test_snake.py` remaps the hardware addresses to low RAM, stubs
`gpio_set`/`spi_cfg`, scripts the keypad and checks movement, reversal
rejection, all four walls, eating/growth/score, tail chasing and body collision.

## Known risks (verify on the device)

- The key bit for **red/end** is inferred from code, not observed; `#` is a
  second exit key in case it is wrong.
- The frame delay is a calibrated busy loop (`DELAY0`); the speed on the real
  CPU is a guess and may need tuning.
- After quitting, the firmware's normal OK handling runs and may open the
  Netzdienste submenu; press back to return.
- If the phone hangs or reboots: battery out, hold **4+6**, reinsert, flash
  the stock (or hardened 116.076.05) image.
