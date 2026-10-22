#!/bin/sh
# build.sh : build/padtest.neo and releases/Neo Geo Controller Test.zip
set -e
cd "$(dirname "$0")"
B=build; mkdir -p $B
python3 tools/mkgfx.py $B/padtest.s1 $B/gfx.inc
vasmm68k_mot -Fsrec -s28 -quiet -Isrc -I$B -o $B/p1.s28 src/padtest.asm
vasmz80_oldstyle -Fbin -quiet -o $B/m1.bin src/m1.z80
python3 tools/mkneo.py $B/p1.s28 $B/padtest.s1 $B/m1.bin $B/padtest.neo
