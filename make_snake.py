#!/usr/bin/env python3
"""Build the Snake firmware image for the SL750H PRO (flashable via USB).

Starts from the stock image, applies the full hardened recipe
(make_hardened.py: version bump, USB string, neutered http URLs), then:
  1. writes the Snake payload (snake/snake.bin, built by snake/build.sh) into
     the erased 0xFF area at file 0x1ce29e = CPU 0x2C1244,
  2. patches the main-menu window handler (CPU 0x16fc1e) at CPU 0x16fc48 /
     file 0x7cca2: `cmpw $0x1a,r7 ; beq 0x16fd82` -> `br 0x2C1244` (6 bytes;
     the 2 bytes after it become dead). The trampoline at 0x2C1244 redoes the
     event compare; on OK (0x1a) with main item 3 (Netzdienste) highlighted it
     runs Snake, then continues into the original OK handling (0x16fd82);
     every other event resumes the compare chain at 0x16fc50,
  3. re-forces crc16(R1[:-2]) to the on-flash value with the 2-byte fixer and
     recomputes every CRC.

Usage: python3 make_snake.py <stock.upd> <out.upd> [new_version]
Default version 116.076.06 (the phone runs the hardened 116.076.05).
"""
import os, struct, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from sl750h_tool import crc16, fix_all_crcs, TABLE

src, dst = sys.argv[1], sys.argv[2]
NEWVER = sys.argv[3] if len(sys.argv) > 3 else '116.076.06'

R1S, R1E, FIX = 0xc05a, 0x3fd05c, 0x3fd056
CPU = lambda off: off + 0xF2FA6          # file offset -> CPU address
PAYLOAD_OFF = 0x1ce29e                   # CPU 0x2C1244
HOOK_OFF = 0x7cca2                       # CPU 0x16fc48
HOOK_OLD = bytes.fromhex('b7521a0000183601')  # cmpw $0x1a,r7 ; beq 0x16fd82
HOOK_NEW = bytes.fromhex('1000e105fc15')      # br 0x2c1244 (long form)
assert CPU(PAYLOAD_OFF) == 0x2C1244 and CPU(HOOK_OFF) == 0x16fc48

with tempfile.TemporaryDirectory() as tmp:
    hard = os.path.join(tmp, 'hardened.upd')
    subprocess.run([sys.executable, os.path.join(HERE, 'make_hardened.py'), src, hard, NEWVER],
                   check=True, stdout=subprocess.DEVNULL)
    d = bytearray(open(hard, 'rb').read())
TARGET = struct.unpack('<H', d[R1E-2:R1E])[0]   # crcB(R1) already equals the on-flash value
patched = []

payload = open(os.path.join(HERE, 'snake', 'snake.bin'), 'rb').read()
area = d[PAYLOAD_OFF:PAYLOAD_OFF+len(payload)]
assert set(area) == {0xff}, 'payload area is not erased (0xFF)'
d[PAYLOAD_OFF:PAYLOAD_OFF+len(payload)] = payload
patched.append(PAYLOAD_OFF)
print(f'  snake payload {len(payload)} bytes @ file {PAYLOAD_OFF:#x} (CPU {CPU(PAYLOAD_OFF):#x})')

assert d[HOOK_OFF:HOOK_OFF+len(HOOK_OLD)] == HOOK_OLD, 'unexpected bytes at the hook site'
d[HOOK_OFF:HOOK_OFF+len(HOOK_NEW)] = HOOK_NEW
patched.append(HOOK_OFF)
print(f'  menu hook @ file {HOOK_OFF:#x} (CPU {CPU(HOOK_OFF):#x}): {HOOK_OLD[:6].hex()} -> {HOOK_NEW.hex()}')

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
print('wrote', dst, f'({NEWVER}) - CRCs consistent:', ok)
sys.exit(0 if ok else 1)
