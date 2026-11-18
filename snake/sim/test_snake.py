#!/usr/bin/env python3
"""Run the real Snake CR16 code in the GDB CR16 simulator (cr16-elf-run).

The sim has flat RAM and no peripherals, so the game's hardware addresses are
remapped to low RAM in a test copy of snake.s, gpio_set/spi_cfg are stubbed,
and a scripted keypad drives poll_keys/step. Each scenario checks the dumped
{ret, len, score, head x, head y} per tick against hand-derived expectations.

Run: CR16=<toolchain>/bin python3 snake/sim/test_snake.py
"""
import os, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
B = os.path.join(os.environ.get('CR16', ''), 'cr16-elf-')
# the hook trampoline's firmware targets are never reached in the sim
STUBS = ['--defsym', 'KState=0x10000', '--defsym', 'OKTail=0x10000', '--defsym', 'ChainNext=0x10000']
R, D, L, U = (0x02, 0x04), (0x10, 0x02), (0x02, 0x01), (0x01, 0x02)
REMAP = {'0xff4c00': '0x9000', '0xff4940': '0x9010', '0xff4942': '0x9012',
         '0xff4948': '0x9018', '0x875678': '0x9100', '0x875679': '0x9101',
         '0x8753a0': '0x9104', '0x874630': '0x9108'}

def sh(*a):
    subprocess.run(a, check=True)

def build_core(tmp):
    s = open(os.path.join(HERE, '..', 'snake.s')).read()
    for a, b in REMAP.items():
        s = s.replace(a, b)
    for sym in ('game_new', 'step', 'poll_keys'):
        s = s.replace('\n%s:' % sym, '\n.globl %s\n%s:' % (sym, sym), 1)
    p = os.path.join(tmp, 'core.s'); open(p, 'w').write(s)
    sh(B + 'as', p, '-o', os.path.join(tmp, 'core.o'))

def run(tmp, keys):
    sp = os.path.join(tmp, 'script.s')
    with open(sp, 'w') as f:
        f.write('.section .script,"a"\n')
        for r, c in keys:
            f.write('.byte 0x%02x,0x%02x\n' % (r, c))
        f.write('.byte 0xff,0\n')
    sh(B + 'as', sp, '-o', os.path.join(tmp, 'script.o'))
    sh(B + 'as', os.path.join(HERE, 'harness.s'), '-o', os.path.join(tmp, 'h.o'))
    elf = os.path.join(tmp, 't.elf')
    sh(B + 'ld', *STUBS, '-e', '_start', '-Ttext', '0x10000', '--section-start', '.script=0x50000',
       os.path.join(tmp, 'h.o'), os.path.join(tmp, 'core.o'), os.path.join(tmp, 'script.o'), '-o', elf)
    out = subprocess.run([B + 'run', elf], capture_output=True, check=True).stdout
    return [tuple(out[i:i+5]) for i in range(0, len(out), 5)]

def run_selfhit(tmp):
    # preset body (5,5)(4,5)(4,4)(5,4)(6,4) heading up: next cell (5,4) is segment 3
    sh(B + 'as', os.path.join(HERE, 'selfhit.s'), '-o', os.path.join(tmp, 's.o'))
    elf = os.path.join(tmp, 's.elf')
    sh(B + 'ld', *STUBS, '-e', '_start', '-Ttext', '0x10000', os.path.join(tmp, 's.o'),
       os.path.join(tmp, 'core.o'), '-o', elf)
    return subprocess.run([B + 'run', elf], capture_output=True, check=True).stdout

def main():
    with tempfile.TemporaryDirectory() as tmp:
        build_core(tmp)
        fails = 0
        def check(name, ok):
            nonlocal fails
            print(('ok:   ' if ok else 'FAIL: ') + name)
            fails += not ok
        # start: head (7,9) moving right, length 3; seed 0x1234 puts food at (14,13)
        t = run(tmp, [R, R, R, D, D, U, U, L, L, L])
        check('movement + 180-degree reversal rejected',
              [(x, y) for _, _, _, x, y in t] ==
              [(8, 9), (9, 9), (10, 9), (10, 10), (10, 11), (10, 12), (10, 13), (9, 13), (8, 13), (7, 13)]
              and all(r == 0 for r, *_ in t))
        t = run(tmp, [R] * 7 + [D] * 4 + [R])
        check('eating food grows length and score', t[10][:3] == (0, 4, 1) and t[10][3:] == (14, 13))
        check('right wall collides', t[11][0] == 1)
        t = run(tmp, [D] + [L] * 8)
        check('left wall collides', t[7][3:] == (0, 10) and t[8][0] == 1)
        t = run(tmp, [U] * 10)
        check('top wall collides', t[8][3:] == (7, 0) and t[9][0] == 1)
        t = run(tmp, [D] * 11)
        check('bottom wall collides', t[8][3:] == (7, 18) and t[9][0] == 1)
        t = run(tmp, [R] * 7 + [D] * 4 + [L, U, R, D])
        check('chasing the vacated tail is allowed', all(r == 0 for r, *_ in t) and t[-1][3:] == (14, 13))
        out = run_selfhit(tmp)
        check('running into the body collides', out == b'\x01')
    sys.exit(1 if fails else 0)

if __name__ == '__main__':
    main()
