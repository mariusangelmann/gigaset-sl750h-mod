#!/usr/bin/env python3
"""Live test: dial a number from the PC by injecting key presses.

Uploads the variable key stub (0x878880, flag 0x878903, key byte 0x878904),
posts each digit with a short pause (the key queue holds only 8 entries), then
green. Logs the call state ([0x8744C0]) and presses red HOLD seconds after the
call started.

Usage: CR16=<toolchain>/bin dial.py <number> [hold_s]
"""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mon, presskey

number = sys.argv[1]
HOLD = float(sys.argv[2]) if len(sys.argv) > 2 else 20
S, F, K = 0x878880, 0x878903, 0x878904
t0 = time.time()
log = lambda m: print('%6.1fs %s' % (time.time() - t0, m), flush=True)

def press(code):
    mon.one('B%X,%X' % (K, code))
    return presskey.fire(S, F)

presskey.upload(None, S, F, key=K)
log('stub uploaded; dialling %s' % number)
for ch in number:
    r = press(presskey.NAMES[ch])
    log('digit %s -> %s' % (ch, 'ok' if r == 0x600D else repr(r)))
    time.sleep(0.3)
log('green -> %r' % press(0x22))
t_call = None
while time.time() - t0 < 120:
    incall = mon.read_many(['8744C0'])['8744C0']
    if incall and t_call is None:
        t_call = time.time(); log('call started ([0x8744C0]=1)')
    if t_call and time.time() - t_call >= HOLD:
        log('red -> %r' % press(0x23)); break
    if t_call and not incall:
        log('call ended by the other side'); break
time.sleep(2)
log('[0x8744C0] = %r' % mon.read_many(['8744C0'])['8744C0'])
