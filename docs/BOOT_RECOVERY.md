# Boot loader (R0) and 4+6 recovery

Question: if we replace R1 with our own firmware, can a broken image still be
recovered over USB with 4+6? Answer from static analysis: **yes, as long as R0
is never modified.**

## Image regions (header at `.upd` offset 0x04/0x20/0x3C)

| Region | Type | File range | CPU range | Version | Role |
|---|---|---|---|---|---|
| R0 | 4 | 0x58–0xC05A (48 KB) | 0xF3000–0xFF000 | 116.038.00 | boot loader + USB updater |
| R1 | 1 | 0xC05A–0x3FD05C | 0xFF000–0x4F0000 | 116.076.xx | application (what we patch/replace) |
| R2 | 6 | 0x3FD05C–end | 0x4F0000–0x80C004 | 116.005.00 | data/resources (not analysed yet) |

The updater re-reads only regions whose header CRC changed, so every flash we
have done so far rewrote R1 only (R0 and R2 had zero reads in the logs).

## Evidence that R0 is the recovery path

Disassembly: `cr16-elf-objdump -D -b binary -m cr16 --adjust-vma=0xf2ffe r0.bin`.

- **R0 is the reset code.** At 0xF300E it loads `intbase` (0xF3400), sets the
  stacks and `cfg`, clears/fills RAM, then initialises GPIO (0xF3180).
- **It runs its updater from RAM.** 0xF30A8 copies 0xF3400–0xF3484 to RAM
  0x810000 and 0xF3484–0xFBEF0 to RAM 0x810100, the usual pattern for code
  that must keep running while flash is erased.
- **It has its own USB update client.** The protocol strings `AT^SRSR`,
  `AT^SSWU`, `AT^SGBD`, `AT^SSWR`, `AT^SERR` appear in R0 (file 0x93BA–0x9C1A)
  as well as in R1.
- **It checks a two-key combo itself.** 0xF44AE configures the keypad matrix
  GPIOs, drives P1.2 low and reads P3 bit 5, then drives P1.0 low and reads P3
  bit 3, returning 1 only if both are seen. Its caller (0xF466E, in R0's boot
  state machine) on a hit initialises the updater path and sets RAM state
  0x8000A0 = 2. This is the hold-keys-at-power-up recovery.
- R0 has ~2960 branches inside itself and only a handful of decoded targets
  outside it, which look like data misdecoded as code. Nothing indicates R0
  depends on R1.

## Not proven yet

- That the combo checked at 0xF44AE is exactly 4+6 (the column/row polarity
  was not fully decoded). The owner's recovery procedure says 4+6.
- R0's behaviour when R1's CRC is invalid (it may also fall into update mode
  on its own).

## Rule for the custom firmware

Never write R0. Build images by replacing R1 content only, keep R0 bytes and
the R0 header entry identical to stock. Before the first flash of our own R1,
optionally do a live test: battery out, hold 4+6, battery in, and check that
the USB port shows up in update mode.
