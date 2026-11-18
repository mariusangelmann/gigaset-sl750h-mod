# Custom UI (live from RAM, no flashing)

C code for the custom firmware's UI, tested on the handset through the AT
monitor (`AT^GCTRACER`), so nothing is flashed.

- `fw.h`: stock-firmware routines and registers we use. They are bound to
  addresses in `ram.ld`.
- `lcd.c` / `lcd.h`: ST7789 driver (fill, text, label). It uses the
  firmware's SPI routines, as in `re/DISPLAY.md`.
- `fontgen.py`: turns Spleen BDF fonts (`fonts/`, BSD-2) into C tables
  covering ASCII plus äöüÄÖÜß°.
- `menutest.c`: a scrolling list menu steered with the phone's keys.
- `build.sh`: builds `build/menutest.bin`, linked at RAM 0x876000.
- `run.py`: uploads the binary (about 2.5 min at ~60 bytes/s) and runs it.
  On exit the program presses OK and then red itself, so the stock UI
  repaints the whole screen.

## Toolchain

GCC 12 and newer dropped CR16 (`cc0` was removed), so use GCC 11.5.0 with
`gcc-11.5.0-arm64-darwin.patch` (arm64 macOS host hooks). Build it like this:
configure with `--target=cr16-elf --enable-languages=c --without-headers
--with-newlib --disable-shared --disable-multilib`, then run
`make all-gcc install-gcc all-target-libgcc install-target-libgcc`.
It is installed in `work/toolchain/prefix`. GCC's register convention matches
the firmware: r0–r6 are scratch and r7 and up are saved. Symbols carry a
leading `_`.

## Rules learned on the handset (2026-11-18)

- **Never block the scheduler.** The first version looped inside a single
  monitor call. The menu showed for about 5 s, then the phone reset, even
  though it kicked the watchdog. So something else, such as the DECT task or a
  supervisor, needs the scheduler to run. Now `start()` does about 10 ms of
  work per call and returns. The monitor re-runs it for as long as the PC keeps
  the port open, at about 68 steps/s. This ran stably for 27 s.
- While our UI runs, it sets the stock key-queue lock (0x874E02) and empties
  the queue (0x14D0B4) on every step. That way the stock UI does not react to
  our key presses.
- **Red always reaches the stock UI.** `post_key` (0x14CE14) unlocks the
  queue for red, so the stock UI jumps to its idle screen, which only draws its
  own elements. It also redraws its clock every minute. The test repaints its
  whole screen about 0.35 s after red or a minute change. A short flash of the
  stock screen remains and can't be avoided without changing flash. The real
  custom firmware won't have this, because the stock UI doesn't draw there.
- On exit the program posts OK (stock menu, full repaint) and then red (clean
  idle screen) itself.
- Keys are read from `KEY_RAW` (0x875678: low byte = row, high byte = column).
  A key counts once it holds for two steps. UP and DOWN repeat while held.
- Timing: 2000 empty-loop iterations take about 3 ms.

Menu: OK on "Info" (or key 9) shows the clock, date and battery, updated live
(verified 2026-11-19). The other entries only show their name in the footer,
which also shows the raw key word for checking the keymap. Data sources:
`re/STATUS.md`.
