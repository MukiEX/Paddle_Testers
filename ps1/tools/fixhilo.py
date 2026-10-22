#!/usr/bin/env python3
"""fixhilo.py <in.s> <out.s> : put two nops after every mflo/mfhi in compiler output.
The R3000 corrupts HI/LO if MULT/DIV starts within two instructions of MFLO/MFHI,
and LLVM's (experimental) MIPS I mode doesn't schedule around it."""
import sys, re
out = []
for l in open(sys.argv[1]):
    out.append(l)
    if re.match(r'\s*(mflo|mfhi)\b', l): out.append('\tnop\n\tnop\n')
open(sys.argv[2], 'w').write(''.join(out))
