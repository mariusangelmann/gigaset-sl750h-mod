# Status data: clock, battery, signal (handset 116.076.09)

## Clock: verified live 2026-11-18

Found by comparing two RAM snapshots of 0x874000..0x876000 taken 80 s apart
(`AT^GCTRACER` reads).

| Address | Type | Meaning | Read 18:36 |
|---|---|---|---|
| 0x87451C | u16 | year | 2026 |
| 0x87451E | u8 | month 1..12 | 11 |
| 0x87451F | u8 | day | 18 |
| 0x874520 | u8 | hour | 18 |
| 0x874521 | u8 | minute | 36 (went 33 → 35 between snapshots) |
| 0x874522 | u8 | weekday, 0 = Monday | 2 (Wednesday) |

A second copy with the same layout sits at 0x87471C. Seconds were not found
in this block.

## Battery: verified via AT and RAM

`AT+CBC` handler 0x100E44 calls `0x11CFF4(2)`. That reads the status table
0x874B92 at index 2, i.e. the byte **0x874B94**, and maps it like this:

| Value | +CBC | Meaning |
|---|---|---|
| 3 / 4 / 5 | 0, 20 / 60 / 100 | on battery, 20 / 60 / 100 % |
| 6 / 7 / 8 | 1, 20 / 60 / 100 | charging, 20 / 60 / 100 % |
| 9 | 1, 0 | charging, empty |

On 2026-11-18 it read 5 (full, on USB). The firmware only keeps these three
levels, matching the stock battery icon.

## Signal: open

`AT+CSQ` handler 0x100DEA reads byte **0x8749CE** through getter 0x14B280.
It divides the value by 20 (capped at 4) and maps it through
{00,07,0F,17,1F}. The byte is written at 0x14B1E4 from the payload of
message 0x42, and it read 0 while idle. It is probably only filled during a
connection (or for Bluetooth) and is not the idle-screen DECT bar. Next step:
a walk test (snapshot RAM near the base, then far away, then near again).
