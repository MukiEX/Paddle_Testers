#!/bin/sh
# build.sh : 0.BIN and "Saturn Controller Test.bin/.cue" in build/
set -e
cd "$(dirname "$0")"
SH=${SH_PREFIX:-sh-elf-}
mkdir -p build
python3 tools/gen.py
${SH}as --isa=sh2 -big -o build/tester.o src/tester.s
${SH}objcopy -O binary -j .text build/tester.o build/0.BIN
python3 tools/mkdisc.py
