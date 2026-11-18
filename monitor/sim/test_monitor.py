#!/usr/bin/env python3
"""Run the real monitor CR16 code (mon_entry) in the GDB CR16 simulator.

The monitor touches no hardware, so monitor.s is assembled unchanged; the
firmware helpers (at_begin, at_send_response_line, at_send_ok, at_send_error)
are stubbed in harness.s to record what the handler did. Each case feeds one
AT tail string, called through a register like the dispatcher does, and checks
the status (OK/ERROR), the captured response line (format + first vararg) and
that callee-saved registers and sp survive. Cases run in order in one sim
session, so memory written by one case is read back by the next.

On a parse failure the monitor is self-diagnosing: it emits three "0x%X" lines
(arg-pointer high word, arg-pointer low word, first 16-bit word at the arg
pointer) and then returns ERROR, so a device failure reveals the real buffer.
In the sim the arg pointer is the case-string pointer, so the third line - the
one the harness captures - equals the first two bytes of the tail as a
little-endian word; that is what the error cases assert.

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
    # --- byte write ---
    ('=B9100,FF', OK, None),            # low byte only
    ('=9100', OK, 0xCAFF),              # high byte of CAFE preserved
    # --- stage a routine (movw $0xABCD,r0; jump (ra)) at 0x9200 and call it ---
    ('=B9200,B0', OK, None),
    ('=B9201,5A', OK, None),
    ('=B9202,CD', OK, None),
    ('=B9203,AB', OK, None),
    ('=B9204,EE', OK, None),
    ('=B9205,0A', OK, None),
    ('=C9200', OK, 0xABCD),  # NOTE sim exec             # call -> reply routine's r0
    ('=9100', OK, 0xCAFF),              # memory still sane after the call
]

CALLEE_ADDR = 0x11000  # harness 'callee' pinned here via --defsym

def sh(*a):
    subprocess.run(a, check=True)

def main():
    with tempfile.TemporaryDirectory() as tmp:
        cp = os.path.join(tmp, 'cases.s')
        with open(cp, 'w') as f:
            f.write('.section .cases,"a"\n')
            for t, *_ in CASES:
                tb=('=C%X'%CALLEE_ADDR if t=='CALLEE' else t).encode()
                f.write('.byte %s\n' % ','.join(str(b) for b in tb + b'\0'))
            f.write('.byte 0xff\n')
        objs = []
        for src, o in ((os.path.join(HERE, '..', 'monitor.s'), 'm.o'),
                       (os.path.join(HERE, 'harness.s'), 'h.o'), (cp, 'c.o')):
            sh(B + 'as', src, '-o', os.path.join(tmp, o))
            objs.append(os.path.join(tmp, o))
        elf = os.path.join(tmp, 't.elf')
        sh(B + 'ld', '-e', '_start', '-Ttext', '0x10000', '--section-start', '.cases=0x50000',
           '--section-start', '.callee=0x%X' % CALLEE_ADDR,
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
        if st == ERR:
            # self-diagnosing: 3 lines; last = first LE word at the arg pointer.
            # In the sim the arg pointer is the case string, so the low byte is
            # the tail's first byte. A second tail byte (when present) is its
            # high byte; for tails shorter than 2 bytes the high byte is the
            # next case string in memory, so it is not asserted.
            tb = tail.encode('latin-1')
            want_lines = 3
            diag_ok = (fp == fmt and (v & 0xFF) == (tb[0] if tb else 0)
                       and (len(tb) < 2 or (v >> 8) == tb[1]))
            good = status == st and lines == want_lines and regs == 1 and begin == 1 and diag_ok
        else:
            want_lines, want_val = (0, None) if val is None else (1, val)
            good = (status == st and lines == want_lines and regs == 1 and begin == 1
                    and (want_val is None or (v == want_val and fp == fmt)))
        got = 'status=%d lines=%d value=0x%04X fmt=0x%X regs=%d begin=%d' % (
            status, lines, v, fp, regs, begin)
        print(('ok:   ' if good else 'FAIL: ') + '%-14r -> %s' % (tail, got))
        fails += not good
    sys.exit(1 if fails else 0)

if __name__ == '__main__':
    main()
