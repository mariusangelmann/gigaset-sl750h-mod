#!/usr/bin/env python3
"""
sl750h_tool.py - USB modding tool for Gigaset SL750H PRO (platform "Shark", kilby build line,
Dialog SC1444x / CR16C SoC). Works over the USB CDC-ACM serial port only - no hardware mods.

Subcommands:
  info                          AT info (model, firmware, URLs)
  files                         list OBEX filesystem (ringtones/pictures)
  upload <local> <remote>       upload file (e.g. /Sounds/99 MyRingtone.L22, /Pictures/x.jpg)
  download <remote> <local>     download file
  ringtone <audio.wav> <name>   convert to G.722 (.L22) via ffmpeg and upload to /Sounds
  flash <image.upd>             flash a (possibly patched) firmware image over USB
  patch <in.upd> <out.upd> <spec>...
                                patch image: spec = @0xOFF:hexbytes or @0xOFF:file.bin or
                                str:0xOFF:"old"=>"new" (same length). Fixes header CRC16.

Protocol (reversed from Gigaset QuickSync Gigaset.Runtime.dll + live capture):
  host -> AT^SRSR 1            query: dev requests header via AT^SGBD 0x0, 0x100,
                               answers AT^SSWU=1,<len> (update required) or =0, then AT^SRSR 0
  host -> AT^SRSR 2            perform: dev walks regions that differ, AT^SGBD <off>,<size>
  host -> <raw block bytes> + "OK\r\n"   (reply to every SGBD)
  dev  -> AT^SSWS / AT^SSWR n / AT^SERR n / AT^SRSR 0   all answered with "OK\r\n"
  after AT^SSWR n the USB device reboots; reopen the port and send AT^SRSR 2 again.

Image format (shark__gqs.bin gunzipped):
  header [0:0x58]: u16 crc @0 = CRC16-CCITT (poly 0x1021, MSB-first, seed 0x55AA)
    over d[2:0x58]; u16 Length @0x02 = 0x58; 3 entries of 28 bytes @0x04/0x20/0x3C:
    [u16 type][u32 ofs][u32 len][12B ver][u32 flags][u16 crc]
  regions R0=[0x58:0xc05a] R1=[0xc05a:0x3fd05c] R2=[0x3fd05c:end], each starting with
    its 12-byte version string, ending with crcA u16 @end-4 = ck(region[:-4]) and
    crcB u16 @end-2 = ck(region[:-2]) (crcB covers crcA); header entry crc = crcB
    (entry@0x3C uses crcA). Last u16 of the file = ck(whole file[:-2]).
  IMPORTANT: at a region end the phone checks the received data against the CRC
  already on flash, so patched content must keep crc16(region[:-2]) unchanged
  (force it with 2 free bytes inside the region - see make_mod.py).
"""
import serial, time, threading, subprocess, re, os, sys, struct, shutil

REOK = b'OK\r\n'
sgbd_re = re.compile(rb'AT\^SGBD (0x[0-9a-fA-F]+), (0x[0-9a-fA-F]+)')

def find_dev():
    r = subprocess.run(['ls', '/dev'], capture_output=True, text=True)
    ds = [f'/dev/{x}' for x in r.stdout.split() if x.startswith('tty.usbmodem')]
    return ds[0] if ds else None

def make_table(poly=0x1021):
    t = []
    for i in range(256):
        c = i << 8
        for _ in range(8):
            c = ((c << 1) ^ poly) & 0xFFFF if c & 0x8000 else (c << 1) & 0xFFFF
        t.append(c)
    return t
TABLE = make_table()
def crc16(seed, data):
    crc = seed
    for b in data:
        crc = ((crc << 8) & 0xFFFF) ^ TABLE[((crc >> 8) ^ b) & 0xFF]
    return crc & 0xFFFF

def fix_header_crc(d):
    L = struct.unpack('<H', d[2:4])[0]
    d[0:2] = struct.pack('<H', crc16(0x55AA, bytes(d[2:L])))
    return d

def fix_all_crcs(d, patched_offsets=None):
    """Recompute CRCs for regions touched by patched_offsets (payload), plus header CRC.
    Layout (verified against stock images):
      header block [0:0x58], crc u16 @0 = crc16(0x55AA, d[2:0x58])
      regions: R0=[0x58:e0.ofs], R1=[e0.ofs:e1.ofs], R2=[e1.ofs:len]
      each region ends with crcA u16 @end-4 = crc16(0x55AA, region[:-4])
      and crcB u16 @end-2 = crc16(0x55AA, region[:-2]).
      header entry crc fields: @0x1E = crcB(R0), @0x3A = crcB(R1), @0x56 = crcA(R2).
    """
    e0ofs = struct.unpack('<I', d[0x22:0x26])[0]
    e1ofs = struct.unpack('<I', d[0x3E:0x42])[0]
    bounds = [0x58, e0ofs, e1ofs, len(d)]
    hdr_crc_off = {0: 0x1E, 1: 0x3A, 2: 0x56}
    for i in range(len(bounds) - 1):
        a, b = bounds[i], bounds[i+1]
        if b - a < 8: continue
        if patched_offsets is not None and not any(a <= o < b for o in patched_offsets):
            continue  # region untouched
        ca = crc16(0x55AA, bytes(d[a:b-4]))
        d[b-4:b-2] = struct.pack('<H', ca)   # write crcA first: crcB covers it
        cb = crc16(0x55AA, bytes(d[a:b-2]))
        d[b-2:b] = struct.pack('<H', cb)
        if i == 0:
            d[0x1E:0x20] = struct.pack('<H', cb)
        elif i == 1:
            d[0x3A:0x3C] = struct.pack('<H', cb)
        elif i == 2:
            d[0x56:0x58] = struct.pack('<H', ca)
            # last region's crcB uses a different rule; leave stored value if region untouched
            if patched_offsets and any(a <= o < b for o in patched_offsets):
                pass  # keep computed crcB for patched last region (best effort)
    fix_header_crc(d)
    # file-level trailer: last u16 = crc16(0x55AA, file[:-2]) over the WHOLE image
    d[-2:] = struct.pack('<H', crc16(0x55AA, bytes(d[:-2])))
    return d

def cmd_patch(args):
    src, dst = args[0], args[1]
    d = bytearray(open(src, 'rb').read())
    patched = []
    for spec in args[2:]:
        if spec.startswith('@'):
            at, payload = spec[1:].split(':', 1)
            off = int(at, 16)
            if payload.endswith('.bin') or os.path.exists(payload):
                data = open(payload, 'rb').read()
            else:
                data = bytes.fromhex(payload)
            d[off:off+len(data)] = data
            patched.append(off)
            print(f'patched {len(data)} bytes at {hex(off)}')
        elif spec.startswith('stru:'):
            m = re.match(r'stru:(0x[0-9a-fA-F]+):"(.*)"=>"(.*)"', spec)
            off = int(m.group(1), 16); old = m.group(2).encode('utf-16le'); new = m.group(3).encode('utf-16le')
            assert len(old) == len(new), 'same length required'
            assert d[off:off+len(old)] == old, f'old not found at {hex(off)}'
            d[off:off+len(new)] = new
            patched.append(off)
            print(f'patched utf16 string at {hex(off)}')
        elif spec.startswith('str:'):
            m = re.match(r'str:(0x[0-9a-fA-F]+):"(.*)"=>"(.*)"', spec)
            off = int(m.group(1), 16); old = m.group(2).encode(); new = m.group(3).encode()
            assert len(old) == len(new), 'same length required'
            assert d[off:off+len(old)] == old, f'old string not found at {hex(off)}: {d[off:off+len(old)]!r}'
            d[off:off+len(new)] = new
            patched.append(off)
            print(f'patched string at {hex(off)}: {old!r} -> {new!r}')
        else:
            raise ValueError('bad spec ' + spec)
    fix_all_crcs(d, patched)
    open(dst, 'wb').write(bytes(d))
    print('wrote', dst, 'header crc', hex(struct.unpack("<H", d[0:2])[0]))

# ---------- serial plumbing ----------
class Link:
    def __init__(self):
        self.ser = None
        self.lock = threading.Lock()
        self.stop = False
        self.linebuf = b''
    def open(self, wait_s=60):
        t0 = time.time()
        while time.time() - t0 < wait_s:
            d = find_dev()
            if d:
                try:
                    s = serial.Serial(d, 9600, timeout=0.2); s.dtr = True; s.rts = False
                    with self.lock: self.ser = s
                    print('[port]', d)
                    threading.Thread(target=self._reader, daemon=True).start()
                    return True
                except Exception:
                    pass
            time.sleep(0.5)
        return False
    def close(self):
        with self.lock:
            try: self.ser.close()
            except Exception: pass
            self.ser = None
    def _reader(self):
        while not self.stop:
            with self.lock: s = self.ser
            if s is None: time.sleep(0.2); continue
            try: b = s.read(4096)
            except Exception: time.sleep(0.2); continue
            if b: self.linebuf += b
    def send(self, b):
        with self.lock:
            if self.ser: self.ser.write(b)
    def at(self, cmd, wait=1.5):
        self.linebuf = b''
        self.send(cmd.encode() + b'\r\n')
        end = time.time() + wait
        out = b''
        while time.time() < end:
            if b'OK\r\n' in self.linebuf or b'ERROR' in self.linebuf:
                out = self.linebuf; break
            time.sleep(0.1)
        return (out or self.linebuf).decode('ascii', 'replace')

def cmd_info(args):
    lk = Link(); lk.open()
    for c in ['AT', 'AT+CGMI', 'AT+CGMM', 'AT+CGMR', 'AT+CGSN', 'AT^WPPN', 'AT^SURL', 'AT^SHSN?', 'AT^SGST', 'AT+CBC', 'AT^HSMM?', 'AT^SQWE?']:
        print(c, '->', lk.at(c).replace('\r', '').strip())
    lk.stop = True; lk.close()

# ---------- flash ----------
def cmd_flash(args):
    fw = open(args[0], 'rb').read()
    lk = Link(); lk.open()
    blocks = errs = reboots = 0
    first = [True]
    phase = ['query']
    def initiate():
        lk.send(b'AT\r\n'); time.sleep(0.8)
        # SRSR 1 = query: device fetches header (SGBD 0x0,0x100) and reports SSWU.
        # SRSR 2 = perform: device walks the regions that differ. Use SRSR 1 on the
        # first connect so the new header (with our entry CRCs) reaches the device;
        # after a reboot, SRSR 2 resumes the walk.
        lk.send(b'AT^SRSR 1\r\n' if first[0] else b'AT^SRSR 2\r\n')
        first[0] = False
    initiate()
    t0 = time.time(); state = 'run'
    while time.time() - t0 < 5400 and state != 'done':
        if lk.linebuf:
            while b'\n' in lk.linebuf:
                line, lk.linebuf = lk.linebuf.split(b'\n', 1)
                s = line.decode('ascii', 'replace').strip()
                if not s: continue
                m = sgbd_re.search(s.encode())
                if m:
                    off = int(m.group(1), 16); size = int(m.group(2), 16)
                    sl = fw[off:off+size]
                    if len(sl) < size: sl += b'\xff' * (size - len(sl))
                    blocks += 1
                    if blocks % 200 == 0: print(f'... {blocks} blocks')
                    with open('/tmp/gig/sgbd_offsets.log', 'a') as f: f.write(f'{off:x} {size:x}\n')
                    lk.send(sl + REOK)
                elif s.startswith(('AT^SSWU', 'AT^SSWS', 'AT^SERR', 'AT^SRSR 0')):
                    if s.startswith('AT^SERR'):
                        errs += 1; print('SERR', s)
                        with open('/tmp/gig/sgbd_offsets.log', 'a') as f: f.write(f'### SERR {s} after block {blocks}\n')
                    if s.startswith('AT^SSWU'): print('SSWU', s)
                    if s.startswith('AT^SRSR 0'): print('device finished (SRSR 0)')
                    lk.send(REOK)
                    if s.startswith('AT^SRSR 0'):
                        if phase[0] == 'query':
                            # query phase ended (SSWU answered); now perform the update
                            phase[0] = 'perform'
                            time.sleep(1.0)
                            lk.send(b'AT^SRSR 2\r\n')
                        else:
                            state = 'done'
                elif s.startswith('AT^SSWR'):
                    print('SSWR reboot:', s)
                    lk.send(REOK); state = 'wait'
                break_inner = None
                if state == 'wait': break
            if state == 'wait':
                lk.close(); time.sleep(3); reboots += 1
                if lk.open(90):
                    state = 'run'; time.sleep(2); initiate()
                else:
                    state = 'done'
        time.sleep(0.05)
    print(f'=== done state={state} blocks={blocks} errs={errs} reboots={reboots}')
    lk.stop = True
    try: lk.send(b'ATZ\r\n')
    except Exception: pass
    time.sleep(1); lk.close()

# ---------- obex file ops (minimal, based on QuickSync4Linux) ----------
QS4L_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'QuickSync4Linux')
def qs4l(*args):
    env = dict(os.environ, PYTHONPATH=QS4L_ROOT + os.pathsep + os.environ.get('PYTHONPATH', ''))
    return subprocess.run([sys.executable, '-m', 'QuickSync4Linux', '-d', find_dev(), *args], env=env)

def cmd_files(args):
    qs4l('listfiles')

def cmd_upload(args):
    qs4l('upload', args[1], '--file', args[0])

def cmd_download(args):
    qs4l('download', args[0], '--file', args[1])

def cmd_ringtone(args):
    src, name = args[0], args[1]
    out = '/tmp/' + name + '.L22'
    ff = shutil.which('ffmpeg') or '/opt/homebrew/bin/ffmpeg'
    r = subprocess.run([ff, '-y', '-i', src, '-ar', '16000', '-ac', '1', '-c:a', 'g722', '-f', 'g722', out], capture_output=True)
    if r.returncode != 0:
        print(r.stderr.decode()[-500:]); sys.exit(1)
    remote = '/Sounds/' + name + '.L22'
    cmd_upload([out, remote])

USAGE = __doc__
def main():
    if len(sys.argv) < 2: print(USAGE); sys.exit(1)
    cmd = sys.argv[1]; args = sys.argv[2:]
    {'info': cmd_info, 'flash': cmd_flash, 'patch': cmd_patch,
     'files': cmd_files, 'upload': cmd_upload, 'download': cmd_download,
     'ringtone': cmd_ringtone}[cmd](args)

if __name__ == '__main__':
    main()
