# Display: drawing our own pixels (verified on the handset)

`monitor/stubs/fillrect.s`, run from RAM (0x879000) via `AT^GCTRACER=C879000`,
draws a filled rectangle with the firmware's own LCD primitives:
`gpio_set` 0x1DA3E6 (CS = pin 6, 1 = selected; D/C = pin 0x2F, 1 = command),
`spi_cfg` 0x1DCE12 (r4 = 0 8-bit / 1 16-bit, clock 2 if [0x874630] bit 4 else 1),
`spi_w8` 0x1DCE5E, `spi_w16` 0x1DCE82. Sequence: CASET 0x2A, RASET 0x2B,
RAMWR 0x2C, pixels as 16-bit words, then CASET/RASET back to 0..239 / 0..319 and
CS released. It calls no task-0 path, so no deadlock.

Result 2026-11-18: a rectangle X 40..199, Y 100..199 appeared where expected
and stayed (the stock UI only redraws dirty areas).

**Colours: plain RGB565, stored as native words.** `spi_w16` reads
little-endian words from memory and sends each one high byte first. The first
stubs stored colours high byte first (`.byte c>>8, c&0xff`), so every colour
arrived byte-swapped. That first looked like inversion (0x07E0 green showed as
magenta-ish 0xE007), but the text test proved it is a swap: white 0x0000-sent
showed black and blue showed purple (0xE0FF). Both stubs now use `.word`.
Verified 2026-11-18: white text on pure blue.

## Text (verified on the handset)

`monitor/drawtext.py "TEXT" [x y scale fg bg]` renders text with a 5x7 font on
the PC into a 1-bit bitmap and runs `monitor/stubs/blit1bpp.s` from RAM: it
expands each bitmap row (MSB = left pixel) into a pixel line at 0x879C00, sends
it with `spi_w16` and kicks the watchdog per row. "Hallo!" at (24,215), scale 4,
drew correctly on the first run (2026-11-18). The font only has the glyphs
used so far; a full font comes with the custom UI.

The first single run showed nothing visible to the owner; three repeated runs
did. Cause not established (possibly screen dimmed or just missed).
