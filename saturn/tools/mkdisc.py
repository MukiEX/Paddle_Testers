#!/usr/bin/env python3
"""Build a Saturn bootable MODE1/2352 bin/cue: IP.BIN (system area) + ISO9660 root with 0.BIN."""
import os, sys, struct
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from cdsec import fix_mode1

def both16(v): return struct.pack('<H', v) + struct.pack('>H', v)
def both32(v): return struct.pack('<I', v) + struct.pack('>I', v)
DATE7 = bytes([126, 10, 18, 12, 0, 0, 0])        # 2026-10-18 12:00 GMT
def date17(): return b'2026101812000000' + b'\0'

def dirrec(name, lba, size, isdir):
    n = len(name)
    l = 33 + n + (1 - n % 2)
    r = bytes([l, 0]) + both32(lba) + both32(size) + DATE7 + bytes([2 if isdir else 0, 0, 0]) + both16(1) + bytes([n]) + name
    return r + b'\0' * (l - len(r))

def build(ip, prog, title, outbase, total=600):
    ip = bytearray(ip)
    def field(off, n, s): ip[off:off + n] = s.encode().ljust(n)[:n]
    field(0x20, 10, 'T-PADTEST'); field(0x2A, 6, 'V1.000'); field(0x30, 8, '20261018')
    field(0x60, 0x70, title)
    sysarea = bytes(ip).ljust(16 * 2048, b'\0')
    ROOT, PROG = 20, 21
    psec = (len(prog) + 2047) // 2048
    root = dirrec(b'\0', ROOT, 2048, True) + dirrec(b'\1', ROOT, 2048, True) + dirrec(b'0.BIN;1', PROG, len(prog), False)
    root = root.ljust(2048, b'\0')
    pt_l = bytes([1, 0]) + struct.pack('<I', ROOT) + struct.pack('<H', 1) + b'\0\0'
    pt_m = bytes([1, 0]) + struct.pack('>I', ROOT) + struct.pack('>H', 1) + b'\0\0'
    pvd = bytearray(2048)
    pvd[0:8] = b'\x01CD001\x01\0'
    pvd[8:40] = b'SEGA SEGASATURN'.ljust(32)
    pvd[40:72] = b'SATURN_CONTROLLER_TEST'.ljust(32)
    pvd[80:88] = both32(total)
    pvd[120:124] = both16(1); pvd[124:128] = both16(1); pvd[128:132] = both16(2048)
    pvd[132:140] = both32(len(pt_l) - 0)
    pvd[140:144] = struct.pack('<I', 18); pvd[148:152] = struct.pack('>I', 19)
    pvd[156:190] = dirrec(b'\0', ROOT, 2048, True)
    for off, n in ((190, 128), (318, 128), (446, 128), (574, 128), (702, 37), (739, 37), (776, 37)):
        pvd[off:off + n] = b' ' * n
    pvd[318:318 + 6] = b'CLAUDE'
    for off in (813, 830, 847, 864): pvd[off:off + 17] = (date17() if off < 847 else b'0' * 16 + b'\0')
    pvd[881] = 1
    term = b'\xffCD001\x01'.ljust(2048, b'\0')
    user = [sysarea[i:i + 2048] for i in range(0, len(sysarea), 2048)]
    user += [bytes(pvd), term, pt_l.ljust(2048, b'\0'), pt_m.ljust(2048, b'\0'), root]
    p = prog.ljust(psec * 2048, b'\0')
    user += [p[i:i + 2048] for i in range(0, len(p), 2048)]
    assert len(user) <= total
    user += [bytes(2048)] * (total - len(user))
    with open(outbase + '.bin', 'wb') as f:
        for lba, u in enumerate(user):
            m, s = divmod(lba + 150, 75); mi, se = divmod(m, 60)
            bcd = lambda v: (v // 10) << 4 | v % 10
            sec = bytearray(2352)
            sec[0:12] = b'\0' + b'\xff' * 10 + b'\0'
            sec[12:16] = bytes([bcd(mi), bcd(se), bcd(s), 1])
            sec[16:16 + 2048] = u
            f.write(fix_mode1(sec))
    name = os.path.basename(outbase)
    open(outbase + '.cue', 'w').write('FILE "%s.bin" BINARY\n  TRACK 01 MODE1/2352\n    INDEX 01 00:00:00\n' % name)

if __name__ == '__main__':
    # IP.BIN from Jo Engine (MIT): Sega security code, all four area codes (JTUE), and an AIP
    # that starts the first file (0.BIN) at 0x06004000. Only the header text is changed here.
    ip = open(os.path.join(HERE, '..', 'third_party', 'IP.BIN'), 'rb').read()
    prog = open(os.path.join(HERE, '..', 'build', '0.BIN'), 'rb').read()
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, '..', 'build', 'Saturn Controller Test')
    build(ip, prog, 'SATURN CONTROLLER TEST', out)
    print('wrote', os.path.normpath(out))
