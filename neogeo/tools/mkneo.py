"""Pack the pad tester into a .neo (TerraOnion/MiSTer format, unencrypted)."""
import struct, sys

def main(p_srec, s_rom, m_rom, out):
    p = bytearray(b'\xff' * 0x100000)
    for line in open(p_srec):
        line = line.strip()
        if not line.startswith('S') or line[1] not in '123':
            continue
        alen = {'1': 2, '2': 3, '3': 4}[line[1]]
        n = int(line[2:4], 16)
        raw = bytes.fromhex(line[4:4 + n * 2])
        a = int.from_bytes(raw[:alen], 'big')
        d = raw[alen:-1]
        p[a:a + len(d)] = d
    p[0::2], p[1::2] = p[1::2], p[0::2]          # .neo P ROM is word-swapped
    s = open(s_rom, 'rb').read()
    m = open(m_rom, 'rb').read().ljust(0x20000, b'\0')
    v = b'\0' * 0x80000
    c = b'\0' * 0x100000
    hdr = bytearray(4096)
    hdr[0:4] = b'NEO\x01'
    struct.pack_into('<6I', hdr, 4, len(p), len(s), len(m), len(v), 0, len(c))
    struct.pack_into('<I', hdr, 0x1c, 2026)                     # year
    struct.pack_into('<I', hdr, 0x20, 0)                        # genre: other
    struct.pack_into('<I', hdr, 0x24, 0)                        # screenshot
    struct.pack_into('<I', hdr, 0x28, 0x0420)                   # NGH
    hdr[0x2c:0x2c + 33] = b'Pad + Spinner Test'.ljust(33, b'\0')
    hdr[0x4d:0x4d + 17] = b'MukiEX'.ljust(17, b'\0')
    open(out, 'wb').write(bytes(hdr) + bytes(p) + s + m + v + c)

if __name__ == '__main__':
    main(*sys.argv[1:5])
