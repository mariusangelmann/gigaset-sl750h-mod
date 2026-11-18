#!/usr/bin/env python3
"""Live test: answer an incoming call and hang up from the PC.

Uploads a green-key stub (0x878800, flag 0x878900) and a red-key stub
(0x878840, flag 0x878901), then polls the call state: when the handset rings
([0x8744C0]=1, [0x8744BE] bit 2 = 0) it presses green; HOLD seconds after the
call is active it presses red. Prints a timeline.

Usage: CR16=<toolchain>/bin calltest.py [timeout_s] [hold_s]
"""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mon, presskey

TIMEOUT = float(sys.argv[1]) if len(sys.argv) > 1 else 300
HOLD = float(sys.argv[2]) if len(sys.argv) > 2 else 5
G, GF, R, RF = 0x878800, 0x878900, 0x878840, 0x878901
presskey.upload(0x22, G, GF)
presskey.upload(0x23, R, RF)
t0 = time.time()
log = lambda m: print('%6.1fs %s' % (time.time() - t0, m), flush=True)
log('stubs uploaded; waiting for an incoming call')
phase, t_active = 'wait', None
while time.time() - t0 < TIMEOUT:
    v = mon.read_many(['8744C0', '8744BE'])
    incall, active = v['8744C0'], (v['8744BE'] or 0) & 4
    if phase == 'wait' and incall and not active:
        log('ringing -> press GREEN: result %r' % presskey.fire(G, GF)); phase = 'answered'
    elif phase == 'answered' and active:
        log('call active'); t_active = time.time(); phase = 'talk'
    elif phase == 'talk' and time.time() - t_active >= HOLD:
        log('press RED: result %r' % presskey.fire(R, RF)); phase = 'hungup'
    elif phase == 'hungup' and not incall:
        log('call ended'); break
    if phase == 'answered' and not incall:
        log('call ended before it became active'); break
else:
    log('timeout in phase %s' % phase)
