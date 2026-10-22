#!/bin/sh
# build.sh : PADTEST.EXE and "PS1 Controller Test.bin/.cue" in build/
set -e
cd "$(dirname "$0")"
B=build; mkdir -p $B
python3 tools/gen.py $B/gen.h
CF="--target=mipsel-unknown-elf -march=mips1 -mabi=32 -msoft-float -mno-abicalls -fno-pic -G0 -O2 -ffreestanding -fno-builtin -nostdlib -fomit-frame-pointer -Wno-unknown-warning-option -I$B"
clang $CF -c src/crt0.S -o $B/crt0.o
clang $CF -Wall -Wno-misleading-indentation -Wno-empty-body -S src/main.c -o $B/main.s
python3 tools/fixhilo.py $B/main.s $B/main.fixed.s
clang $CF -c $B/main.fixed.s -o $B/main.o
ld.lld -T src/link.ld -o $B/padtest.elf $B/crt0.o $B/main.o
llvm-objcopy -O binary $B/padtest.elf $B/padtest.raw
python3 tools/hazards_elf.py $B/padtest.elf
python3 tools/mkexe.py $B/padtest.raw $B/PADTEST.EXE 0x$(llvm-nm $B/padtest.elf | awk '$3=="_start"{print $1}')
printf 'BOOT = cdrom:\\PADTEST.EXE;1\r\nTCB = 4\r\nEVENT = 10\r\nSTACK = 801FFF00\r\n' > $B/SYSTEM.CNF
python3 tools/mkiso.py "$B/PS1 Controller Test.bin" "$B/PS1 Controller Test.cue" PADTEST SYSTEM.CNF=$B/SYSTEM.CNF PADTEST.EXE=$B/PADTEST.EXE
