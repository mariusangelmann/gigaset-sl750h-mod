#!/usr/bin/env python3
"""Snapshot a list of monitor addresses to a file, or diff two snapshots.

snap.py save <file> <hexaddr...>   read each addr once, write "addr val" lines
snap.py diff <fileA> <fileB>       print addresses whose value changed
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mon

def save(path, addrs):
    vals = mon.read_many(addrs)              # fast batch read (one open port)
    out = ['%s %s' % (a.upper(), ('%X' % vals[a.upper()]) if vals.get(a.upper()) is not None else 'ERR')
           for a in addrs]
    open(path, 'w').write('\n'.join(out) + '\n')
    for l in out: print(l)

def diff(fa, fb):
    da = dict(l.split() for l in open(fa) if l.split())
    db = dict(l.split() for l in open(fb) if l.split())
    for a in da:
        if a in db and da[a] != db[a]:
            print('%s: %s -> %s' % (a, da[a], db[a]))

if __name__ == '__main__':
    if sys.argv[1] == 'save':
        save(sys.argv[2], sys.argv[3:])
    elif sys.argv[1] == 'diff':
        diff(sys.argv[2], sys.argv[3])
