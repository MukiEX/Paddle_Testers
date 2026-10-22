# CD-ROM Mode 2 Form 1 EDC/ECC (ECMA-130)
import numpy as np
_edc=[0]*256
for i in range(256):
    e=i
    for _ in range(8): e=(e>>1)^(0xD8018001 if e&1 else 0)
    _edc[i]=e
def edc(data):
    e=0
    for b in data: e=(e>>8)^_edc[(e^b)&0xff]
    return e
_f=[0]*256; _b=[0]*256
for i in range(256):
    j=(i<<1)^(0x11d if i&0x80 else 0); _f[i]=j&0xff; _b[i^j&0xff]=i
def _ecc_compute(src, major_count, minor_count, major_mult, minor_inc, dest_off, sec):
    size=major_count*minor_count
    for major in range(major_count):
        index=(major>>1)*major_mult+(major&1)
        ecc_a=0; ecc_b=0
        for minor in range(minor_count):
            temp=src[index]
            index+=minor_inc
            if index>=size: index-=size
            ecc_a^=temp; ecc_b^=temp; ecc_a=_f[ecc_a]
        ecc_a=_b[_f[ecc_a]^ecc_b]
        sec[dest_off+major]=ecc_a
        sec[dest_off+major+major_count]=ecc_a^ecc_b
def fix_mode2form1(sec):
    """sec: bytearray(2352) with sync/header/subheader/data filled"""
    e=edc(sec[16:16+8+2048])
    sec[2072:2076]=e.to_bytes(4,'little')
    hdr=bytes(sec[12:16]); sec[12:16]=b'\0\0\0\0'
    src=sec[12:]  # copy view as bytes
    buf=bytearray(sec)
    # P parity: over 0x800+... standard: src offset 12, 86 major, 24 minor, mult 2, inc 86
    _ecc_compute(memoryview(buf)[12:], 86, 24, 2, 86, 2076, buf)
    _ecc_compute(memoryview(buf)[12:], 52, 43, 86, 88, 2248, buf)
    buf[12:16]=hdr
    sec[:]=buf
def check(sec):
    s=bytearray(sec); fix_mode2form1(s); return s==bytearray(sec)
