# USB firmware-update protocol (reversed from QuickSync's Gigaset.Runtime.dll + live capture)

Transport: USB CDC-ACM serial (`/dev/tty.usbmodem*` on macOS, COMx on Windows).
Line discipline: AT commands end with `\r`; host answers data blocks with
`OK\r\n`.

Two roles, distinguished by the SRSR argument:

- `AT^SRSR 1` — **query**. Phone requests the image header:
  `AT^SGBD 0x00000000, 0x00000100`. Host replies `fw[0:0x100] + "OK\r\n"`.
  Phone compares the header's target version with the running one and answers
  `AT^SSWU=1, 0x003F1000` (update required; 2nd field = region length) or
  `AT^SSWU=0` (not required), then `AT^SRSR 0` (end of query). Host acks every
  line with `OK\r\n`.
- `AT^SRSR 2` — **perform**. Phone walks the regions whose entry version differs
  from the on-flash header, in ~0x3FB-byte chunks: `AT^SGBD <off>, <size>` ->
  host replies `<raw block> + "OK\r\n"`. At each region end the phone verifies the
  region CRC (see IMAGE_FORMAT.md) and reports `AT^SERR 0` (CRC) / `1` (interface) /
  `2` (transmit) on failure. `AT^SSWR <n>` = reboot (USB re-enumerates; reopen
  the port and send `AT^SRSR 2` again). `AT^SRSR 0` = update finished.

Rules learned live:

- Version strings must stay **numeric and increasing** — `116.M0D.02` is rejected
  as "not required" (the phone parses the version); use e.g. `116.076.04`.
- Flashing takes ~25 min (the phone paces the ~7300 blocks at ~5/s).
- The phone auto-recovered to stock after every interrupted flash in testing —
  it has never bricked. Emergency recovery: battery out, hold **4+6**, reinsert
  battery, plug USB, flash the stock image (emergency mode always accepts it).

## OBEX (files / ringtones / pictures)

- `AT^SQWE=3` enters OBEX mode — only accepted while the handset has a DECT link
  to its base (`AT+CSQ` > 0, `AT^SGST` = 1,1). Put it on the charger/base first.
- `AT^SURL` is read-only and still reports the old update URL from the encrypted
  flashdisk config — that is why we recommend `sl750h_tool.py flash` over
  QuickSync on a PC.
- Filesystem: `/Sounds` (G.722 `.L22`, 16 kHz mono), `/Pictures` (JPG, no EXIF,
  q<=80, 320x240), `/Clip Pictures` (172x240).
