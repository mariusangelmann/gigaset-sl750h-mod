#!/usr/bin/env python3
"""Press one key on the handset from the PC, without flashing.

Assembles monitor/stubs/presskey.s for the given key code, uploads it to RAM
0x878800 with the AT monitor, clears the one-shot flag and calls it.

Usage: CR16=<toolchain>/bin presskey.py <key>
  key: green | red | ok | 0-9 | * | # | a hex code such as 0x22
"""
import os, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import mon

BASE, FLAG = 0x878800, 0x878900
NAMES = {'green': 0x22, 'red': 0x23, 'ok': 0x19, '*': 0x4A, '#': 0x4B}
NAMES.update({str(i): 0x40 + i for i in range(10)})
B = os.path.join(os.environ.get('CR16', ''), 'cr16-elf-')

def build(code, flag=FLAG):
    with tempfile.TemporaryDirectory() as t:
        o, e, b = (os.path.join(t, x) for x in ('p.o', 'p.elf', 'p.bin'))
        subprocess.run([B + 'as', '--defsym', 'CODE=%d' % code, '--defsym', 'FLAG=%d' % flag,
                        os.path.join(HERE, 'stubs', 'presskey.s'), '-o', o], check=True)
        subprocess.run([B + 'ld', '-Ttext', '0x10000', '-e', 'press', o, '-o', e], check=True)
        subprocess.run([B + 'objcopy', '-O', 'binary', e, b], check=True)
        return open(b, 'rb').read()

def upload(code, base=BASE, flag=FLAG):
    """Upload a stub for `code` to `base` (one-shot flag at `flag`), disarmed."""
    blob = build(code, flag)
    if len(blob) % 2: blob += b'\0'
    for i in range(0, len(blob), 2):
        w = blob[i] | blob[i + 1] << 8
        _, ok, _ = mon.one('%X,%X' % (base + i, w))
        if not ok: raise SystemExit('upload failed at %#x' % (base + i))
    if mon.one('%X' % (base + 2))[0] != (blob[2] | blob[3] << 8):
        raise SystemExit('upload verify failed')
    mon.one('B%X,1' % flag)                       # disarmed until fire()

def fire(base=BASE, flag=FLAG):
    """Arm the flag and run an uploaded stub: posts its key exactly once."""
    mon.one('B%X,0' % flag)
    return mon.one('C%X' % base)[0]

def press(code):
    upload(code)
    return fire()

if __name__ == '__main__':
    k = sys.argv[1].lower()
    code = NAMES[k] if k in NAMES else int(k, 0)
    r = press(code)
    print('posted key 0x%02X' % code if r == 0x600D else 'no post (result %r)' % r)
