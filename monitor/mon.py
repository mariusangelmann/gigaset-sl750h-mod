#!/usr/bin/env python3
"""Single-shot client for the on-device AT memory monitor (^GCTRACER).

The monitor works, but the firmware's set-syntax ('=') dispatch re-invokes the
handler in a loop until the input line is consumed, which our handler does not
do - so one `AT^GCTRACER=...` yields the same reply thousands of times until the
port is closed. This client sends ONE command, reads just the first reply, then
immediately closes the port to halt the loop. That makes reads, writes, byte
writes and calls each happen effectively once (a write re-run with the same
value is idempotent; a call is stopped after the first reply so it is not run
thousands of times).

Usage:
  mon.py <hexaddr>                 read  16-bit word at addr      -> prints 0x<val>
  mon.py <hexaddr> <hexval>        write 16-bit word
  mon.py B <hexaddr> <hexval>      write low byte
  mon.py C <hexaddr>              call code at addr (jal), prints routine r0
  mon.py raw '=<...>'              send a raw ^GCTRACER argument

Examples:
  mon.py 875678          # keypad row bitmask (0 = no key pressed)
  mon.py 9100 BEEF ; mon.py 9100
Env: MON_PORT overrides the serial port.
"""
import os, re, sys, time
import serial

PORT = os.environ.get('MON_PORT', '/dev/cu.usbmodem250945661')

def one(arg):
    """Send one ^GCTRACER=<arg> on a fresh port, read just the first reply, then
    close. The firmware re-dispatches the set syntax in a loop until the port is
    closed; closing halts it, and a short settle lets it stop before the next
    command, so each call reads/writes effectively once. The first reply already
    carries the correct value (the handler reads the same address every
    iteration). Returns (value_or_None, raw_text)."""
    s = serial.Serial(PORT, 115200, timeout=0.15)
    try:
        time.sleep(0.15); s.reset_input_buffer()
        s.write(('AT^GCTRACER=%s\r\n' % arg).encode())
        buf = b''; t = time.time()
        while time.time() - t < 1.2:          # read to the first terminator
            c = s.read(256)
            if c: buf += c
            if b'OK' in buf or b'ERROR' in buf:
                break
    finally:
        s.reset_input_buffer()
        s.close()                             # closing halts the re-dispatch loop
    time.sleep(0.4)                           # let the device go quiet before the next call
    txt = buf.decode('latin-1')
    # look at the first reply only (up to the first terminator)
    iok, ierr = txt.find('OK'), txt.find('ERROR')
    first_ok = iok != -1 and (ierr == -1 or iok < ierr)
    head = txt[:iok if iok != -1 else (ierr if ierr != -1 else len(txt))]
    m = re.search(r'0x([0-9A-Fa-f]+)', head)
    val = int(m.group(1), 16) if m else None
    return val, first_ok, txt

def read_many(addrs, port=None):
    """Fast batch read: keep one port open and echo-sync each reply so the
    firmware's re-dispatch flood from the previous command can't bleed into the
    next. ~0.01s per address. Returns {addr_upper: value_or_None}. Use this (not
    repeated one()) when reading many addresses or capturing fast-changing state
    such as live menu navigation; closing the port at the end halts the loop."""
    s = serial.Serial(port or PORT, 115200, timeout=0.05)
    out = {}
    try:
        time.sleep(0.15); s.reset_input_buffer()
        for a in addrs:
            cmd = 'AT^GCTRACER=%s' % a
            s.reset_input_buffer()
            s.write((cmd + '\r\n').encode())
            buf = b''; t = time.time(); val = None
            while time.time() - t < 0.6:
                c = s.read(128)
                if c: buf += c
                i = buf.find(cmd.encode())       # sync on this command's echo
                if i >= 0:
                    after = buf[i + len(cmd):]
                    m = re.search(rb'0x([0-9A-Fa-f]+)', after)
                    if m: val = int(m.group(1), 16); break
                    if b'ERROR' in after: break
            out[a.upper()] = val
    finally:
        s.reset_input_buffer(); s.close()
    time.sleep(0.3)
    return out

def main(a):
    if not a:
        print(__doc__); return 2
    if a[0] == 'raw':
        val, ok, txt = one(a[1])
        sys.stdout.write(txt)
        return 0
    is_write = False
    if a[0] in ('B', 'C'):
        arg = a[0] + ''.join(a[1:])          # e.g. B9100,FF  or  C9200
        is_write = a[0] == 'B'
    elif len(a) == 1:
        arg = a[0]                           # read
    else:
        arg = '%s,%s' % (a[0], a[1])         # write addr,val
        is_write = True
    val, ok, txt = one(arg)
    if is_write:                             # write/byte-write reply is just OK
        if ok:
            print('OK'); return 0
        sys.stderr.write('ERROR\n' + txt); return 1
    if val is None:                          # read/call expect a 0x value
        sys.stderr.write('ERROR\n' + txt); return 1
    print('0x%X' % val)
    return 0

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
