"""CD-ROM Mode 1 sector EDC/ECC (ECMA-130)."""
EDC_TAB = []
for i in range(256):
    e = i
    for _ in range(8): e = (e >> 1) ^ (0xD8018001 if e & 1 else 0)
    EDC_TAB.append(e)
GF_EXP = [0] * 512; GF_LOG = [0] * 256
x = 1
for i in range(255):
    GF_EXP[i] = x; GF_LOG[x] = i
    x <<= 1
    if x & 0x100: x ^= 0x11D
for i in range(255, 512): GF_EXP[i] = GF_EXP[i - 255]
ECC_F = [0] * 256; ECC_B = [0] * 256
for i in range(256):
    j = (i << 1) ^ (0x11D if i & 0x80 else 0)
    ECC_F[i] = j & 0xFF; ECC_B[i ^ j & 0xFF] = i

def edc(data):
    e = 0
    for b in data: e = EDC_TAB[(e ^ b) & 0xFF] ^ (e >> 8)
    return e

def _ecc_block(sec, major_count, minor_count, major_mult, minor_inc, dest):
    size = major_count * minor_count
    for major in range(major_count):
        index = (major >> 1) * major_mult + (major & 1)
        a = b = 0
        for minor in range(minor_count):
            t = sec[0xC + index]
            index += minor_inc
            if index >= size: index -= size
            a ^= t; b ^= t; a = ECC_F[a]
        a = ECC_B[ECC_F[a] ^ b]
        sec[dest + major] = a
        sec[dest + major + major_count] = a ^ b

def fix_mode1(sec):
    """sec: bytearray(2352) with sync/header/user data; rewrites EDC (0x810) and ECC (0x81C..)."""
    e = edc(sec[0:0x810])
    sec[0x810:0x814] = e.to_bytes(4, 'little')
    sec[0x814:0x81C] = b'\0' * 8
    _ecc_block(sec, 86, 24, 2, 86, 0x81C)   # P
    _ecc_block(sec, 52, 43, 86, 88, 0x8C8)  # Q
    return sec
