#!/usr/bin/env python3
"""mkiso.py <out.bin> <out.cue> <volume id> NAME=path ... : single-track MODE2/2352 PS1 disc image.
Minimal ISO 9660: root directory only, files stored contiguously. No licence sectors."""
import sys, os, struct, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdsec import fix_mode2form1
out_bin, out_cue, volid = sys.argv[1:4]
files = [(a.split('=', 1)[0], open(a.split('=', 1)[1], 'rb').read()) for a in sys.argv[4:]]
PVD, TERM, PTL, PTM, ROOT = 16, 17, 18, 19, 20
lba = 21; layout = []
for name, data in files:
    n = max(1, (len(data) + 2047) // 2048); layout.append((name, data, lba, n)); lba += n
total = lba + 150                                  # trailing empty sectors
t = time.gmtime(0 + 1792000000)
def both16(v): return struct.pack('<H', v) + struct.pack('>H', v)
def both32(v): return struct.pack('<I', v) + struct.pack('>I', v)
recdate = bytes([t.tm_year - 1900, t.tm_mon, t.tm_mday, t.tm_hour, t.tm_min, t.tm_sec, 0])
def dirrec(name, lba, size, flags):
    n = name if isinstance(name, bytes) else name.encode()
    r = bytearray(33 + len(n)); r += b'\0' * (len(r) & 1)
    r[0] = len(r); r[2:10] = both32(lba); r[10:18] = both32(size); r[18:25] = recdate
    r[25] = flags; r[28:32] = both16(1); r[32] = len(n); r[33:33 + len(n)] = n
    return bytes(r)
root = dirrec(b'\0', ROOT, 2048, 2) + dirrec(b'\1', ROOT, 2048, 2)
for name, data, l, n in layout: root += dirrec(name + ';1', l, len(data), 0)
assert len(root) <= 2048
def vdate(): return time.strftime('%Y%m%d%H%M%S', t).encode() + b'00\0'
pvd = bytearray(2048)
pvd[0] = 1; pvd[1:6] = b'CD001'; pvd[6] = 1
pvd[8:40] = b'PLAYSTATION'.ljust(32); pvd[40:72] = volid.encode().ljust(32)
pvd[80:88] = both32(total); pvd[120:124] = both16(1); pvd[124:128] = both16(1); pvd[128:132] = both16(2048)
pvd[132:140] = both32(10); pvd[140:144] = struct.pack('<I', PTL); pvd[148:152] = struct.pack('>I', PTM)
pvd[156:190] = dirrec(b'\0', ROOT, 2048, 2)
for o, l in ((190, 128), (318, 128), (446, 128), (702, 37), (739, 37), (776, 37)): pvd[o:o + l] = b' ' * l
pvd[574:702] = b'PLAYSTATION'.ljust(128)
pvd[813:830] = vdate(); pvd[830:847] = vdate(); pvd[847:864] = b'0' * 16 + b'\0'; pvd[864:881] = b'0' * 16 + b'\0'
pvd[881] = 1
term = bytearray(2048); term[0] = 255; term[1:6] = b'CD001'; term[6] = 1
ptl = bytearray(2048); ptl[0] = 1; ptl[2:6] = struct.pack('<I', ROOT); ptl[6:8] = struct.pack('<H', 1)
ptm = bytearray(2048); ptm[0] = 1; ptm[2:6] = struct.pack('>I', ROOT); ptm[6:8] = struct.pack('>H', 1)
user = {PVD: (pvd, 0x09), TERM: (term, 0x89), PTL: (ptl, 0x89), PTM: (ptm, 0x89), ROOT: (bytearray(root.ljust(2048, b'\0')), 0x89)}
for name, data, l, n in layout:
    for k in range(n):
        user[l + k] = (bytearray(data[k * 2048:(k + 1) * 2048].ljust(2048, b'\0')), 0x89 if k == n - 1 else 0x08)
def bcd(v): return (v // 10) * 16 + v % 10
with open(out_bin, 'wb') as f:
    for s in range(total):
        sec = bytearray(2352)
        sec[0:12] = b'\0' + b'\xff' * 10 + b'\0'
        a = s + 150; sec[12:16] = bytes([bcd(a // 4500), bcd(a // 75 % 60), bcd(a % 75), 2])
        d, sm = user.get(s, (bytearray(2048), 0x20 if s >= lba else 0x08))
        if s >= lba: sm = 0x00                      # empty trailing sectors: plain form 1
        sub = bytes([0, 0, sm, 0]); sec[16:24] = sub + sub; sec[24:2072] = d
        fix_mode2form1(sec); f.write(sec)
open(out_cue, 'w').write('FILE "%s" BINARY\r\n  TRACK 01 MODE2/2352\r\n    INDEX 01 00:00:00\r\n' % os.path.basename(out_bin))
print(out_bin, total, 'sectors')
