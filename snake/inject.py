#!/usr/bin/env python3
"""Inject a compiled CR16C payload (snake.bin) into a SL750H firmware image.

- payload goes to the free 0xFF region at file offset CODE_OFF (default 0x1ce29e)
- optional boot hook: patch the first bytes of the R1 entry (file 0xc06a) with a
  `bal` to the payload; the payload must end by jumping back to HOOK_BACK
- version strings bumped so the phone accepts the update
- crc16(R1[:-2]) forced back to the on-flash value 0xBE12 via the 2-byte fixer,
  then crcA / header CRCs / global file CRC recomputed

Usage: python3 inject.py <in.upd> <out.upd> <snake.bin> [--hook] [new_version]
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sl750h_tool import crc16, fix_all_crcs, TABLE

CODE_OFF = 0x1ce29e          # free space in R1 (CPU 0x2be29e, flash base 0xF0000)
HOOK_SITE = 0xc06a           # R1 entry (first instruction of app init)
R1S, R1E = 0xc05a, 0x3fd05c
FIX = 0x3fd056

src, dst, binpath = sys.argv[1], sys.argv[2], sys.argv[3]
hook = '--hook' in sys.argv[4:]
newver = sys.argv[4] if len(sys.argv) > 4 and not sys.argv[4].startswith('--') else '116.076.06'
oldver = '116.076.02'

payload = open(binpath, 'rb').read()
assert len(payload) < 0x30000, f'payload too big: {len(payload)}'

d = bytearray(open(src, 'rb').read())
patched = []

def putstr(off, old, new):
    o, n = old.encode(), new.encode()
    assert len(o) == len(n) and d[off:off+len(o)] == o, f'mismatch at {off:#x}'
    d[off:off+len(n)] = n; patched.append(off)

for off in (0x2A, 0xC05A, 0x18299D):
    putstr(off, oldver, newver)

# place payload in free space
d[CODE_OFF:CODE_OFF+len(payload)] = payload
patched.append(CODE_OFF)
print(f'payload {len(payload)} bytes at {CODE_OFF:#x} (CPU {CODE_OFF+0xF0000:#x})')

if hook:
    # bal (ra), disp  — CR16C 24-bit form: 00 C0 + 24-bit disp? Use assembler output
    # instead: we expect snake.bin to provide a `hook_patch` symbol; here we emit a
    # raw long-branch. bal encoding (medium): 0x00 0xC0 followed by 3 bytes? We
    # verify against the disassembler after assembling; for now write via assembler
    # helper in build.sh. This function just records the intent.
    patched.append(HOOK_SITE)
    print(f'hook requested at {HOOK_SITE:#x} — do the bal patch in build.sh (see README)')

# CRC fixer: keep crcB(R1) at on-flash value
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

fix_all_crcs(d, patched)
open(dst, 'wb').write(bytes(d))
r = bytes(d)
ok = (struct.unpack('<H', r[0:2])[0] == crc16(0x55AA, r[2:0x58])
      and struct.unpack('<H', r[R1E-2:R1E])[0] == crc16(0x55AA, r[R1S:R1E-2]) == TARGET
      and struct.unpack('<H', r[-2:])[0] == crc16(0x55AA, r[:-2]))
print('wrote', dst, '- CRCs consistent:', ok)
sys.exit(0 if ok else 1)
