#!/usr/bin/env python3
"""Build the firmware image with the AT memory monitor (and Snake) over USB.

Starts from the Snake image (make_snake.py: hardened recipe + Snake payload +
Netzdienste hook), then:
  1. writes the monitor payload (monitor/monitor.bin, built by monitor/build.sh
     with MON_BASE=0x2c1900) into free flash at file 0x1ce95a = CPU 0x2C1900,
     right after Snake's payload,
  2. repoints the ^GCTRACER AT-command handler to the monitor: the handler/2
     field of AT table record 29 at file 0x183324 (CPU 0x2762ca),
     `92 09 08 00` (-> 0x101324) becomes mon_entry/2,
  3. re-forces crc16(R1[:-2]) with the 2-byte fixer and recomputes all CRCs.

The monitor adds AT^GCTRACER=<hexaddr> (read a 16-bit word, replies "0x<VAL>")
and AT^GCTRACER=<hexaddr>,<hexval> (write a 16-bit word), over the normal USB
serial port. This is the fast RE loop: read/write live memory without flashing.

Usage: python3 make_monitor.py <stock.upd> <out.upd> [new_version]
Default version 116.076.07.
Prereq: build monitor/monitor.bin at MON_BASE=0x2c1900 and snake/snake.bin first.
"""
import os, struct, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from sl750h_tool import crc16, fix_all_crcs, TABLE

src, dst = sys.argv[1], sys.argv[2]
NEWVER = sys.argv[3] if len(sys.argv) > 3 else '116.076.07'

R1S, R1E, FIX = 0xc05a, 0x3fd05c, 0x3fd056
CPU = lambda off: off + 0xF2FA6
MON_BASE_CPU = 0x2C1900
MON_OFF = MON_BASE_CPU - 0xF2FA6          # file 0x1ce95a
HOOK_OFF = 0x183324                       # ^GCTRACER handler/2 field (CPU 0x2762ca)
HOOK_OLD = bytes.fromhex('92090800')      # 0x80992 -> handler 0x101324
HOOK_NEW = struct.pack('<I', MON_BASE_CPU // 2)
assert CPU(MON_OFF) == MON_BASE_CPU and CPU(HOOK_OFF) == 0x2762ca

with tempfile.TemporaryDirectory() as tmp:
    snake = os.path.join(tmp, 'snake.upd')
    subprocess.run([sys.executable, os.path.join(HERE, 'make_snake.py'), src, snake, NEWVER],
                   check=True, stdout=subprocess.DEVNULL)
    d = bytearray(open(snake, 'rb').read())
TARGET = struct.unpack('<H', d[R1E-2:R1E])[0]
patched = []

payload = open(os.path.join(HERE, 'monitor', 'monitor.bin'), 'rb').read()
area = d[MON_OFF:MON_OFF+len(payload)]
assert set(area) == {0xff}, 'monitor area is not erased (0xFF) - does Snake overlap it?'
d[MON_OFF:MON_OFF+len(payload)] = payload
patched.append(MON_OFF)
print(f'  monitor payload {len(payload)} bytes @ file {MON_OFF:#x} (CPU {MON_BASE_CPU:#x})')

assert d[HOOK_OFF:HOOK_OFF+4] == HOOK_OLD, 'unexpected bytes at the ^GCTRACER handler field'
d[HOOK_OFF:HOOK_OFF+4] = HOOK_NEW
patched.append(HOOK_OFF)
print(f'  ^GCTRACER handler @ file {HOOK_OFF:#x} (CPU 0x2762ca): {HOOK_OLD.hex()} -> {HOOK_NEW.hex()}')

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
