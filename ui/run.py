#!/usr/bin/env python3
"""Upload ui/build/menutest.bin to RAM 0x876000 and run it on the handset.

Keeps the serial port open while the program runs in steps (red key or ~30 s
without keys ends it) and prints how long it ran. Afterwards it presses OK and
red through monitor/presskey.py so the stock UI redraws the whole screen.

Usage: CR16=<toolchain>/bin run.py [--no-restore] [bin]
"""
import os, re, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'monitor'))
import mon, serial

BASE = 0x876000

def run(addr, timeout):
    """Start the stepped program at addr and keep the port open: the monitor
    re-runs the call (one step each) until the port closes. Stops when a step
    returns 0x0E0D. Returns (steps, seconds, finished)."""
    s = serial.Serial(mon.PORT, 115200, timeout=0.1)
    steps = 0; done = False; t0 = time.time()
    try:
        time.sleep(0.15); s.reset_input_buffer()
        s.write(('AT^GCTRACER=C%X\r\n' % addr).encode())
        buf = b''
        while time.time() - t0 < timeout and not done:
            buf += s.read(4096)
            ms = list(re.finditer(rb'0x([0-9A-Fa-f]+)\s', buf))
            steps += len(ms)
            done = any(int(m.group(1), 16) == 0x0E0D for m in ms)
            buf = buf[ms[-1].end():] if ms else buf[-32:]
    finally:
        s.close()                             # closing stops the re-dispatch
        time.sleep(0.4)
    return steps, time.time() - t0, done

def main(a):
    path = next((x for x in a if not x.startswith('--')),
                os.path.join(HERE, 'build', 'menutest.bin'))
    blob = open(path, 'rb').read()
    t = time.time()
    mon.write_blob(BASE, blob)                # also resets the program's state
    print('uploaded %d bytes in %.0f s' % (len(blob), time.time() - t), flush=True)
    steps, secs, done = run(BASE, 600)
    print('%s after %.1f s, %d steps (%.0f/s)' % ('finished' if done else 'stopped',
          secs, steps, steps / secs))
    if '--no-restore' not in a and done:
        import presskey
        for k in (0x19, 0x23):                # OK opens the menu, red returns: full redraw
            presskey.press(k); time.sleep(0.5)

if __name__ == '__main__':
    main(sys.argv[1:])
