# Security hardening — why, and what was done (verified live on running 116.076.05)

## Why self-service: the vendor is dead for this model

Research findings (2026): Gigaset AG went insolvent (2023); since April 2024 the
DECT business runs as **Gigaset Technologies GmbH (VTech)**. The *PRO* line is
still serviced (N870/N530 bases to V2.71.x in 2026, S700H/SL800H/R700H handsets
to V13.04, March 2025 — but in a different image format, not flashable onto
this 7.4 MB shark layout). The **SL750H PRO is consumer-only and is NOT in the
maintained list**: the consumer server still serves only 116.076.02 (built
12/2019), `suota.gigaset.net/shark_pro_hs/suota.php` is live but returns an
empty update, and archive.org shows no newer shark_pro_hs file. Conclusion: **no
vendor security updates will ever come for this handset** — the fix is to patch
it ourselves over USB, which this toolkit does.

## Attack surface and mitigations (flashed into 116.076.05 via `make_hardened.py`)

| Surface | Risk | Mitigation flashed |
|---|---|---|
| OTA update over plain HTTP (`suota.php`, `update.gigaset.net`, `profile.gigaset.net`) — CRC-only verification means a MITM can push arbitrary firmware (the April 2021 Gigaset supply-chain attack class) | critical, remote | all 18 `http://` URL hosts in R1 replaced with DNS-dead ones (`gigaset.xxx`, `ddns.xxx`, `x`*n). Network firmware push is now impossible; updates only via USB with an image you verify |
| `hxipservicecp.ddns.net:3456` service endpoint — the ddns name no longer resolves (lapsed; re-registrable by an attacker) | high, remote | host neutered |
| leftover test/telemetry endpoints incl. `http://52.31.73.211:8080/api/v1/req/7C2F808E2AFB/...` (leaks device id) and AWS IP `54.93.162.144` | medium | all neutered |
| AT flash interface over USB (`AT^SRSR`/`AT^SGBD`) has no authentication — anyone with the cable can flash | physical access only | kept intentionally (it is our update path); treat the USB port as a trusted boundary |
| OBEX filesystem (`AT^SQWE=3`) — requires DECT base link + USB | physical | unchanged; works when the handset is on its base |
| DECT radio (DSC cipher / auth — known academic weaknesses, comsecuris 2011, iacr 2024/404) | inherent to DECT, not fixable in handset firmware | keep base+handset pairing private, don't register unknown handsets |
| `AT^SURL` still reports the old `update.gigaset.net` URL — the value lives in the persistent (encrypted) flashdisk config, not the patchable R1 strings | low (only consumed by QuickSync on a PC) | **do not run QuickSync**; use `sl750h_tool.py flash` with sha256-verified images |

## Applying future fixes

```
python3 make_hardened.py <stock.upd> <out.upd> <newver>   # neuter URLs + version bump + CRC fixer
python3 sl750h_tool.py patch <out.upd> <out2.upd> 'str:...' ...   # add your own patches
python3 sl750h_tool.py flash <out2.upd>
```

Bump the numeric version each time (the phone rejects non-numeric or
non-increasing versions). Keep R0/R2 and the radio sections untouched (keep their
CRCs at the on-flash values — the CRC fixer handles this automatically).
