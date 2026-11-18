# Gigaset SL750H PRO — USB firmware toolkit (modding / customizing / self-service security updates)

> ## AI disclosure
> This project was created with substantial AI assistance (Mistral Vibe, a CLI
> coding agent). The protocol reverse-engineering, image-format analysis, CRC
> model, flash tooling, firmware patches and documentation were produced in
> AI-assisted sessions and verified by live testing against a real SL750H PRO
> handset over USB (patched firmware 116.076.05 was flashed and is running on
> the author's device). No proprietary Gigaset code or copyrighted assets are
> redistributed; only original tooling, documentation, and locally regenerated
> firmware update images are involved. Use at your own risk.

> ## Scope & intent (please read — this is defensive research on the author's own device)
> Everything in this repo targets **one personally owned Gigaset SL750H PRO
> handset**, connected by its own USB cable. The vendor stopped shipping
> security updates for this model (see `docs/SECURITY_HARDENING.md`), so this
> toolkit exists to **patch and harden that device ourselves** (disable its
> plaintext-HTTP update channels, customize labels, add local features like a
> Snake game) and to keep it recoverable. It contains **no** attack tooling:
> no DECT interception/decryption, no targeting of other people's devices or
> networks, no exploits against third parties. All work is done over the
> device's own documented USB AT interface. If you use this repo, use it on
> hardware you own. See `SECURITY.md`.

Everything here works **over the USB cable only** (the phone shows up as a
"Gigaset Generic CDCACM Device" USB serial port, `/dev/tty.usbmodem*` on macOS,
COMx on Windows). No opening the phone, no soldering, no debug adapter.

Status: **patched firmware images were flashed over USB and the phone booted
them** — `AT+CGMR` reports the hardened `116.076.05`, and the USB device
enumerates as `SL750H-PRO MODDED USB CDC ACM`.

## What the phone is

- Product: SL750H PRO; platform codename reported over USB (`AT+CGMM`): **"Shark"**
  (build line "kilby"). "Lion" (seen in QuickSync) is just an *entry type* in the
  update image format, not this phone's platform.
- SoC: Dialog SC1444x family (CR16C+ CPU), external QSPI NOR flash.
- Stock firmware: 116.076.02 (latest ever shipped, built 12/2019). Download:
  `curl http://update.gigaset.net/firmware/shark_pro_hs/shark__gqs.bin | gunzip > shark_gqs.upd`
  (the phone itself tells you this URL: `AT^SURL`).

## Quickstart

```bash
pip install pyserial          # + ffmpeg if you want ringtone conversion
python3 sl750h_tool.py info                          # talk to the phone over USB
python3 sl750h_tool.py patch shark_gqs.upd out.upd 'str:0x2A:"116.076.02"=>"116.076.99"'
python3 make_hardened.py shark_gqs.upd hardened.upd 116.076.06   # security hardening recipe
python3 sl750h_tool.py flash hardened.upd           # ~25 min, phone paces the transfer
```

Recovery if anything goes wrong: battery out, hold **4+6**, reinsert battery →
emergency mode → `python3 sl750h_tool.py flash shark_gqs.upd`. Details in
`docs/RE_NOTES.md`.

## Layout

```
├── sl750h_tool.py            main CLI: info / files / upload / download / ringtone / patch / flash
├── make_mod.py               recipe: version bump + USB string mod (proven, flashed)
├── make_hardened.py          recipe: security hardening (URL neutering + version bump + CRC fixer)
├── make_snake.py             recipe: hardened + Snake on main menu "Netzdienste" (116.076.06)
├── snake/                    CR16C Snake payload: snake.s, build.sh, sim/ tests, build-toolchain.sh
├── QuickSync4Linux/          vendored third-party OBEX client (MIT), used by files/upload/download
├── docs/
│   ├── PROTOCOL.md           USB flash protocol (AT^SRSR/^SSWU/^SGBD/^SSWR/^SERR), reversed + live-captured
│   ├── IMAGE_FORMAT.md       .upd image layout, region/entry CRCs, the CRC-fixer fixed-point rule
│   ├── SECURITY_HARDENING.md vendor-EOL research + attack-surface table + what was mitigated
│   └── RE_NOTES.md           address mapping, display/keypad/menu/scheduler internals, gas traps, recovery
├── examples/                 ready-to-run example scripts (custom strings, hardening, ringtones)
├── tests/                    offline tests (CRC vectors, image parse/fix round-trip)
└── SECURITY.md               scope & responsible use
```

`.upd` binaries are intentionally not committed (`.gitignore`) — regenerate
them locally from the stock download URL above.

## Docs

- [USB flash protocol](docs/PROTOCOL.md)
- [Image format & CRC model](docs/IMAGE_FORMAT.md)
- [Security hardening (why & what)](docs/SECURITY_HARDENING.md)
- [Reverse-engineering notes](docs/RE_NOTES.md)
- [Snake mod](snake/README.md)
- [Changelog of firmware patches](CHANGELOG.md)
- [Scope & responsible use](SECURITY.md)

## Tool reference

`python3 sl750h_tool.py <cmd>`

- `info` — AT info dump (model, firmware, URLs)
- `files` — list the phone's OBEX filesystem (/Sounds, /Pictures, /Clip Pictures)
- `upload <local> <remote>` / `download <remote> <local>` — e.g. custom ringtones
  (`/Sounds/VibeMod.L22`, G.722 codec, 16 kHz mono) and pictures (JPG, no EXIF,
  q<=80; clip 172x240, full 320x240)
- `ringtone <audio.wav> <name>` — convert (G.722) + upload a ringtone in one step
- `patch <in.upd> <out.upd> <spec>...` — patch the firmware image (same-length
  replacements) and recompute all CRCs.
  spec: `str:0xOFF:\"old\"=>\"new\"` (ASCII), `stru:0xOFF:...` (UTF-16LE),
  `@0xOFF:hexbytes` or `@0xOFF:file.bin`
- `flash <image.upd>` — flash an image over USB (stock or patched)

Note for OBEX commands (`files`/`upload`/`ringtone`): the phone only accepts
`AT^SQWE=3` (enter OBEX) while it has a DECT link to its base (`AT+CSQ` > 0,
`AT^SGST` = 1,1). Put the handset on the charger/base first if these fail.

## Tests

```bash
python3 tests/test_image.py        # CRC vectors + image round-trip (uses stock image if present)
CR16=<toolchain>/bin python3 snake/sim/test_snake.py   # Snake game logic in the CR16 simulator
```
