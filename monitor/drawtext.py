#!/usr/bin/env python3
"""Draw a line of text on the handset's display from the PC, without flashing.

Renders the text with a built-in 5x7 font (scaled) into a 1-bit bitmap, builds
monitor/stubs/blit1bpp.s around it, uploads it to RAM 0x879000 and runs it.
Colours are plain RGB565.

Usage: CR16=<toolchain>/bin drawtext.py "TEXT" [x y scale fg bg]
"""
import os, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import mon

B = os.path.join(os.environ.get('CR16', ''), 'cr16-elf-')
BASE, FLAG = 0x879000, 0x879800

# 5x7 glyphs, one string per row, '#' = set.
FONT = {
    ' ': ['     '] * 7,
    '!': ['  #  ', '  #  ', '  #  ', '  #  ', '  #  ', '     ', '  #  '],
    'H': ['#   #', '#   #', '#   #', '#####', '#   #', '#   #', '#   #'],
    'a': ['     ', '     ', ' ### ', '    #', ' ####', '#   #', ' ####'],
    'l': [' ##  ', '  #  ', '  #  ', '  #  ', '  #  ', '  #  ', ' ### '],
    'o': ['     ', '     ', ' ### ', '#   #', '#   #', '#   #', ' ### '],
}

def render(text, scale):
    cols = []
    for ch in text:
        g = FONT[ch]
        for c in range(5):
            cols.append([g[r][c] == '#' for r in range(7)])
        cols.append([False] * 7)                     # 1 px gap
    pad = 2                                           # border, unscaled px
    w = (len(cols) + 2 * pad) * scale
    w = (w + 7) // 8 * 8
    h = (7 + 2 * pad) * scale
    rows = []
    for y in range(h):
        gy = y // scale - pad
        bits = []
        for x in range(w):
            gx = x // scale - pad
            bits.append(0 <= gy < 7 and 0 <= gx < len(cols) and cols[gx][gy])
        row = bytearray()
        for i in range(0, w, 8):
            v = 0
            for b in bits[i:i + 8]:
                v = v << 1 | b
            row.append(v)
        rows.append(bytes(row))
    return w, h, b''.join(rows)

def build(x, y, w, h, fg, bg, bitmap):
    with tempfile.TemporaryDirectory() as t:
        open(os.path.join(t, 'bitmap.bin'), 'wb').write(bitmap)
        o, e, b = (os.path.join(t, n) for n in ('t.o', 't.elf', 't.bin'))
        d = lambda k, v: ['--defsym', '%s=%d' % (k, v)]
        subprocess.run([B + 'as', '-I', t, *d('X0', x), *d('Y0', y), *d('W', w), *d('H', h),
                        *d('FG', fg), *d('BG', bg),
                        os.path.join(HERE, 'stubs', 'blit1bpp.s'), '-o', o], check=True)
        subprocess.run([B + 'ld', '-T', os.path.join(HERE, 'stubs', 'ram.ld'),
                        '--defsym', 'gpio_set=0x1da3e6', '--defsym', 'spi_cfg=0x1dce12',
                        '--defsym', 'spi_w8=0x1dce5e', '--defsym', 'spi_w16=0x1dce82',
                        o, '-o', e], check=True, stderr=subprocess.DEVNULL)
        subprocess.run([B + 'objcopy', '-O', 'binary', e, b], check=True)
        return open(b, 'rb').read()

def main(a):
    text = a[0]
    x, y, scale = (int(v) for v in (a[1:4] if len(a) >= 4 else (24, 215, 4)))
    fg = int(a[4], 0) if len(a) > 4 else 0xFFFF       # white
    bg = int(a[5], 0) if len(a) > 5 else 0x001F       # blue
    w, h, bm = render(text, scale)
    if x + w > 240: raise SystemExit('text too wide: %d px' % w)
    blob = build(x, y, w, h, fg, bg, bm)
    if BASE + len(blob) > FLAG: raise SystemExit('stub too large: %d bytes' % len(blob))
    mon.write_blob(BASE, blob)
    mon.one('B%X,0' % FLAG)
    r = mon.one('C%X' % BASE)[0]
    print('%dx%d at (%d,%d), %d bytes: %s' % (w, h, x, y, len(blob),
          'drawn' if r == 0x600D else 'result %r' % r))

if __name__ == '__main__':
    main(sys.argv[1:])
