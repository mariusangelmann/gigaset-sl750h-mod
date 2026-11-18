#!/usr/bin/env python3
"""Build the security-hardened SL750H PRO firmware image (flashable via USB).

Starting from the stock image, this:
  1. bumps all version strings to a new numeric version (default 116.076.05)
     so the phone accepts the update (it is running a modded 116.076.04),
  2. keeps the modded USB product string,
  3. NEUTERS every plaintext-http:// URL in the main firmware region (R1):
     gigaset.net hosts -> gigaset.xxx (reserved, never resolves),
     IP-literal hosts -> 'x'*len (DNS-dead), ddns host -> ddns.xxx.
     This kills the network attack surface: the 2021-style supply-chain /
     MITM firmware push via suota.gigaset.net / update.gigaset.net /
     profile.gigaset.net over plain HTTP, the lapsed hxipservicecp.ddns.net
     service endpoint, the leftover AWS test server and the telemetry API
     that leaks the device id. After this, firmware updates are only
     possible via the USB flash path with an image you verify yourself.
  4. keeps crc16(R1[:-2]) at the on-flash value 0xBE12 (2-byte CRC fixer in
     the R1 tail padding) so the phone's region-end check passes,
  5. recomputes crcA / header entry CRCs / header CRC / global file CRC.

Usage: python3 make_hardened.py <stock.upd> <out.upd> [new_version]
"""
import sys, os, re, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sl750h_tool import crc16, fix_all_crcs, TABLE

src, dst = sys.argv[1], sys.argv[2]
NEWVER = sys.argv[3] if len(sys.argv) > 3 else '116.076.05'
OLDVER = '116.076.02'
NEWUSB = 'SL750H-PRO MODDED USB CDC ACM'

R1S, R1E = 0xc05a, 0x3fd05c
FIX = 0x3fd056

d = bytearray(open(src, 'rb').read())
patched = []

def putstr(off, old, new):
    o, n = old.encode(), new.encode()
    assert len(o) == len(n) and d[off:off+len(o)] == o, f'mismatch at {off:#x}: {d[off:off+len(o)]!r}'
    d[off:off+len(n)] = n
    patched.append(off)
    print(f'  ver {off:#x}: {old} -> {new}')

for off in (0x2A, 0xC05A, 0x18299D):
    putstr(off, OLDVER, NEWVER)

off = 0x1C2D93
o = 'Gigaset Generic CDCACM Device'.encode('utf-16le')
n = NEWUSB.encode('utf-16le')
assert len(o) == len(n) and d[off:off+len(o)] == o
d[off:off+len(n)] = n; patched.append(off)
print(f'  usb string {off:#x} -> {NEWUSB!r}')

# neuter every http URL host in R1 (same-length, DNS-dead replacements)
url_re = re.compile(rb'http://([!-~]+?)(?=[:/\x00]|$)')
count = 0
for m in url_re.finditer(bytes(d[R1S:R1E])):
    host = m.group(1).decode()
    if b'gigaset.net' in host.encode():
        newhost = host.replace('gigaset.net', 'gigaset.xxx')
    elif 'ddns.net' in host:
        newhost = host.replace('ddns.net', 'ddns.xxx')
    elif re.fullmatch(r'[\d.]+', host):
        newhost = 'x' * len(host)
    else:
        newhost = 'x' * len(host)
    assert len(newhost) == len(host)
    a = R1S + m.start(1)
    d[a:a+len(host)] = newhost.encode()
    patched.append(a)
    count += 1
    print(f'  url host @{a:#x}: {host} -> {newhost}')
print(f'  neutered {count} URL hosts')

# force crc16(R1[:-2]) to the on-flash value so the region-end check passes
TARGET = struct.unpack('<H', d[R1E-2:R1E])[0]
def step(c, b):
    return (((c << 8) & 0xFFFF) ^ TABLE[((c >> 8) ^ b) & 0xFF]) & 0xFFFF
prefix = crc16(0x55AA, bytes(d[R1S:FIX]))
sol = None
for x in range(0x10000):
    cA = step(step(prefix, x & 0xFF), (x >> 8) & 0xFF)
    cB = step(step(cA, cA & 0xFF), (cA >> 8) & 0xFF)
    if cB == TARGET:
        sol = x; break
assert sol is not None
d[FIX:FIX+2] = struct.pack('<H', sol)
patched.append(FIX)
print(f'  CRC fixer @{FIX:#x} = {sol:04x} (crcB(R1) stays {TARGET:04x})')

fix_all_crcs(d, patched)
open(dst, 'wb').write(bytes(d))

r = bytes(d)
ok = (struct.unpack('<H', r[0:2])[0] == crc16(0x55AA, r[2:0x58])
      and struct.unpack('<H', r[R1E-2:R1E])[0] == crc16(0x55AA, r[R1S:R1E-2]) == TARGET
      and struct.unpack('<H', r[R1E-4:R1E-2])[0] == crc16(0x55AA, r[R1S:R1E-4])
      and struct.unpack('<H', r[-2:])[0] == crc16(0x55AA, r[:-2]))
print('wrote', dst, '- CRCs consistent:', ok)
sys.exit(0 if ok else 1)
