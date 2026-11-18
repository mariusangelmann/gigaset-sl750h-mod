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

**Colours are inverted.** Sent 0x07E0 (green), saw magenta = 0xF81F = ~0x07E0.
The panel runs with inversion, so the custom UI writes `~rgb565`.

The first single run showed nothing visible to the owner; three repeated runs
did. Cause not established (possibly screen dimmed or just missed).
