#!/usr/bin/env python3
"""mkexe.py <in.elf.bin> <out.exe> <entry> : wrap a flat binary loaded at 0x80010000 as a PS-X EXE"""
import sys, struct
data = open(sys.argv[1], 'rb').read()
data += b'\0' * (-len(data) % 2048)
h = bytearray(2048)
h[0:8] = b'PS-X EXE'
struct.pack_into('<IIII', h, 0x10, int(sys.argv[3], 0), 0, 0x80010000, len(data))
struct.pack_into('<II', h, 0x30, 0x801FFF00, 0)          # stack top
h[0x4C:0x4C + 55] = b'Sony Computer Entertainment Inc. for North America area'
open(sys.argv[2], 'wb').write(bytes(h) + data)
