#!/usr/bin/env python3
"""Offline tests for the image format / CRC model. No phone needed.

Run: python3 tests/test_image.py [path-to-stock.upd]
If a stock image is given (or found at ./shark_gqs.upd / /tmp/gig/shark_gqs.upd),
round-trip invariants are checked against it; otherwise only CRC vectors run.
"""
import os, struct, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from sl750h_tool import crc16, fix_all_crcs, fix_header_crc

def test_crc_vectors():
    # independent reference vectors (CRC-16/XMODEM and CRC-16/CCITT-FALSE)
    assert crc16(0x0000, b'123456789') == 0x31C3, hex(crc16(0x0000, b'123456789'))
    assert crc16(0xFFFF, b'123456789') == 0x29B1, hex(crc16(0xFFFF, b'123456789'))
    print('ok: crc16 reference vectors (XMODEM 0x31C3, CCITT-FALSE 0x29B1)')

def find_stock():
    cands = [a for a in sys.argv[1:]] + ['shark_gqs.upd', '/tmp/gig/shark_gqs.upd']
    for c in cands:
        if c and os.path.exists(c):
            return c
    return None

def test_stock(path):
    d = bytearray(open(path, 'rb').read())
    assert struct.unpack('<H', d[2:4])[0] == 0x58, 'header Length != 0x58'
    e0 = struct.unpack('<I', d[0x22:0x26])[0]
    e1 = struct.unpack('<I', d[0x3E:0x42])[0]
    assert (0x58, e0, e1) == (0x58, 0xc05a, 0x3fd05c), (hex(e0), hex(e1))
    # header crc valid on stock
    assert struct.unpack('<H', d[0:2])[0] == crc16(0x55AA, bytes(d[2:0x58]))
    # region crcB values stored in header entries match the regions
    for entry_off, a, b in ((0x1E, 0x58, e0), (0x3A, e0, e1)):
        stored = struct.unpack('<H', d[entry_off:entry_off+2])[0]
        assert stored == crc16(0x55AA, bytes(d[a:b-2])), hex(entry_off)
    # global file trailer
    assert struct.unpack('<H', d[-2:])[0] == crc16(0x55AA, bytes(d[:-2]))
    print('ok: stock image header/region/global CRCs consistent')
    # fix_all_crcs must be idempotent
    once = fix_all_crcs(bytearray(d))
    twice = fix_all_crcs(bytearray(once))
    assert bytes(once) == bytes(twice)
    print('ok: fix_all_crcs idempotent on stock image')
    # patch one byte in R1 payload, recompute, verify region crcB invariant
    mod = bytearray(d)
    mod[0x100000] ^= 0xFF
    fix_all_crcs(mod, patched_offsets=[0x100000])
    a, b = e0, e1
    assert struct.unpack('<H', mod[b-2:b])[0] == crc16(0x55AA, bytes(mod[a:b-2]))
    assert struct.unpack('<H', mod[0x3A:0x3C])[0] == crc16(0x55AA, bytes(mod[a:b-2]))
    assert struct.unpack('<H', mod[-2:])[0] == crc16(0x55AA, bytes(mod[:-2]))
    print('ok: patched R1 -> crcB(R1)/entry/global CRCs consistent')

if __name__ == '__main__':
    test_crc_vectors()
    p = find_stock()
    if p:
        test_stock(p)
    else:
        print('note: no stock image found, skipping round-trip tests '
              '(pass path or put shark_gqs.upd in repo root)')
    print('ALL TESTS PASSED')
