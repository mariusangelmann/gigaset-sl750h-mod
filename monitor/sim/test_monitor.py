#!/usr/bin/env python3
"""Run the real monitor CR16 code (mon_entry) in the GDB CR16 simulator.

The monitor touches no hardware, so monitor.s is assembled unchanged; the
firmware helpers (at_begin, at_send_response_line, at_send_ok, at_send_error)
are stubbed in harness.s to record what the handler did. Each case feeds one
AT tail string, called through a register like the dispatcher does, and checks
the status (OK/ERROR), the captured response line (format + first vararg) and
that callee-saved registers and sp survive. Cases run in order in one sim
session, so memory written by one case is read back by the next.

Run: CR16=<toolchain>/bin python3 monitor/sim/test_monitor.py
"""
import os, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
B = os.path.join(os.environ.get('CR16', ''), 'cr16-elf-')
OK, ERR = 1, 2

# (tail, expected status, expected reply value or None for no reply line)
CASES = [
    ('=9100', OK, 0x1234),              # read preset word
    ('=9100,BEEF', OK, None),           # write
    ('=9100', OK, 0xBEEF),              # read-after-write
    ('=9102', OK, 0x5678),              # neighbour untouched
    ('=9102,7', OK, None),              # short value
    ('=9102', OK, 0x0007),
    ('=9100', OK, 0xBEEF),
    ('9100,cafe', OK, None),            # no '=', lower case
    ('=9100', OK, 0xCAFE),
    ('=41234', OK, 0x5A5A),             # address above 16 bits
    ('=41234,1', OK, None),
    ('=41234\r', OK, 0x0001),           # trailing junk after address ignored
    ('=9100,zz', ERR, None),            # malformed value: no write
    ('=9100,', ERR, None),
    ('=9100', OK, 0xCAFE),
    ('=xyz', ERR, None),                # malformed address
    ('=', ERR, None),
    ('', ERR, None),
    ('=,1', ERR, None),
    ('=9100', OK, 0xCAFE),
]

def sh(*a):
    subprocess.run(a, check=True)

def main():
    with tempfile.TemporaryDirectory() as tmp:
        cp = os.path.join(tmp, 'cases.s')
        with open(cp, 'w') as f:
            f.write('.section .cases,"a"\n')
            for t, *_ in CASES:
                f.write('.byte %s\n' % ','.join(str(b) for b in t.encode() + b'\0'))
            f.write('.byte 0xff\n')
        objs = []
        for src, o in ((os.path.join(HERE, '..', 'monitor.s'), 'm.o'),
                       (os.path.join(HERE, 'harness.s'), 'h.o'), (cp, 'c.o')):
            sh(B + 'as', src, '-o', os.path.join(tmp, o))
            objs.append(os.path.join(tmp, o))
        elf = os.path.join(tmp, 't.elf')
        sh(B + 'ld', '-e', '_start', '-Ttext', '0x10000', '--section-start', '.cases=0x50000',
           *objs, '-o', elf)
        syms = subprocess.run([B + 'nm', elf], capture_output=True, text=True, check=True).stdout
        fmt = int(next(l.split()[0] for l in syms.splitlines() if l.endswith(' fmt_hex')), 16)
        out = subprocess.run([B + 'run', elf], capture_output=True, check=True).stdout

    fails = 0
    if len(out) != 12 * len(CASES):
        print('FAIL: got %d bytes of results, expected %d' % (len(out), 12 * len(CASES)))
        sys.exit(1)
    for i, (tail, st, val) in enumerate(CASES):
        r = out[12 * i:12 * i + 12]
        status, lines, v = r[0], r[1], int.from_bytes(r[2:4], 'little')
        fp, regs, begin = int.from_bytes(r[4:8], 'little'), r[8], r[9]
        want_lines = 0 if val is None else 1
        good = (status == st and lines == want_lines and regs == 1 and begin == 1
                and (val is None or (v == val and fp == fmt)))
        got = 'status=%d lines=%d value=0x%04X fmt=0x%X regs=%d begin=%d' % (
            status, lines, v, fp, regs, begin)
        print(('ok:   ' if good else 'FAIL: ') + '%-14r -> %s' % (tail, got))
        fails += not good
    sys.exit(1 if fails else 0)

if __name__ == '__main__':
    main()
