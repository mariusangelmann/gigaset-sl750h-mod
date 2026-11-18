# Scope & responsible use

This repository is a toolkit for working on **one personally owned Gigaset
SL750H PRO handset** over its own USB cable:

- The vendor no longer ships security updates for this model, so the toolkit
  exists to **harden and patch that device ourselves** (see
  `docs/SECURITY_HARDENING.md`).
- It is **not** attack tooling: no DECT interception or decryption, no exploits
  against third-party devices, networks, or services, no credential theft.
- Everything runs against hardware you own, through the device's own USB AT
  interface, and every firmware image you flash should be one you built and
  verified yourself (sha256) from the stock image.
- Keep the stock `shark_gqs.upd` as a recovery image and know the emergency
  recovery procedure (battery out, hold 4+6, reinsert) before flashing
  (`docs/RE_NOTES.md`).
- Treat the phone's flashdisk content as untrusted (the firmware contains a
  `/usr/share/scripts/%s &` script-exec feature).

This project was built with substantial AI assistance (Mistral Vibe) — see the
AI disclosure in `README.md`.
