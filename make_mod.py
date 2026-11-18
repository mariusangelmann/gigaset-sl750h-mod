#!/usr/bin/env python3
"""Build a flashable modded SL750H firmware image from the stock image.

Proven recipe (this exact patch was flashed successfully over USB):
  - bump all three '116.076.02' version strings to a higher NUMERIC version
    (header entry @0x2A, R1 embedded @0xC05A, payload @0x18299D)
  - patch the UTF-16LE USB product string @0x1C2D93
  - force crc16(R1[:-2]) to stay at the on-flash value 0xBE12 by tuning the
    2 padding bytes at 0x3FD056 (CRC16 is linear; solve the fixed point that
    includes the crcA bytes those 2 bytes produce)
  - recompute crcA / entry CRCs / header CRC / global file CRC

Usage: python3 make_mod.py <stock.upd> <out.upd> [new_version] [usb_string]
"""
import sys, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) if (os := __import__('os')) else '.')
from sl750h_tool import crc16, fix_all_crcs, TABLE

src, dst = sys.argv[1], sys.argv[2]
NEWVER = sys.argv[3] if len(sys.argv) > 3 else '116.076.04'
NEWUSB = sys.argv[4] if len(sys.argv) > 4 else 'SL750H-PRO MODDED USB CDC ACM'
OLDVER = '116.076.02'

R1S, R1E = 0xc05a, 0x3fd05c
FIX = 0x3fd056          # 2 bytes of 0xFF padding right before R1's crcA

d = bytearray(open(src, 'rb').read())
patched = []
def putstr(off, old, new):
    o, n = old.encode(), new.encode()
    assert len(o) == len(n) and d[off:off+len(o)] == o, f'pattern mismatch at {off:#x}: {d[off:off+len(o)]!r}'
    d[off:off+len(n)] = n; patched.append(off)
    print(f'patched {off:#x}: {old!r} -> {new!r}')

putstr(0x2A, OLDVER, NEWVER)
putstr(0xC05A, OLDVER, NEWVER)
putstr(0x18299D, OLDVER, NEWVER)
off = 0x1C2D93
o, n = 'Gigaset Generic CDCACM Device'.encode('utf-16le'), NEWUSB.encode('utf-16le')
assert len(o) == len(n) and d[off:off+len(o)] == o
d[off:off+len(n)] = n; patched.append(off)
print(f'patched {off:#x}: USB product string -> {NEWUSB!r}')

# keep crc16(R1[:-2]) at the on-flash value so the phone's region-end check passes
TARGET = struct.unpack('<H', d[R1E-2:R1E])[0]   # stock crcB, e.g. 0xBE12
def step(c, b):
    return (((c << 8) & 0xFFFF) ^ TABLE[((c >> 8) ^ b) & 0xFF]) & 0xFFFF
prefix = crc16(0x55AA, bytes(d[R1S:FIX]))
sol = None
for x in range(0x10000):
    cA = step(step(prefix, x & 0xFF), (x >> 8) & 0xFF)     # crcA = ck(R1[:-4])
    cB = step(step(cA, cA & 0xFF), (cA >> 8) & 0xFF)       # crcB = ck(R1[:-2]), crcA included
    if cB == TARGET:
        sol = x; break
assert sol is not None, 'no 2-byte fixer found'
d[FIX:FIX+2] = struct.pack('<H', sol)
patched.append(FIX)
print(f'CRC fixer at {FIX:#x} = {sol:04x} (keeps crcB(R1) = {TARGET:04x})')

fix_all_crcs(d, patched)
open(dst, 'wb').write(bytes(d))

r = bytes(d)
ok = (struct.unpack('<H', r[0:2])[0] == crc16(0x55AA, r[2:0x58])
      and struct.unpack('<H', r[R1E-2:R1E])[0] == crc16(0x55AA, r[R1S:R1E-2]) == TARGET
      and struct.unpack('<H', r[R1E-4:R1E-2])[0] == crc16(0x55AA, r[R1S:R1E-4])
      and struct.unpack('<H', r[-2:])[0] == crc16(0x55AA, r[:-2]))
print('wrote', dst, '- all CRCs consistent:', ok)
sys.exit(0 if ok else 1)
