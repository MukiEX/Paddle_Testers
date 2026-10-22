#!/usr/bin/env python3
"""hazards_elf.py <elf> : check the compiled code for R3000 load-delay and HI/LO hazards.
Fails the build if a loaded register is read by the next instruction executed
(including a branch target when the load sits in a delay slot), or if MULT/DIV
comes within two instructions of MFLO/MFHI."""
import sys, subprocess, re
dis = subprocess.run(['llvm-objdump', '-d', '-z', '--no-show-raw-insn', sys.argv[1]], capture_output=True, text=True).stdout
ins = {}; order = []
for l in dis.splitlines():
    m = re.match(r'\s*([0-9a-f]+):\s+(\S+)\s*(.*)', l)
    if m:
        a = int(m.group(1), 16); ins[a] = (m.group(2), m.group(3).split('<')[0].strip()); order.append(a)
LOADS = {'lb', 'lbu', 'lh', 'lhu', 'lw', 'lwl', 'lwr'}
BR = {'b', 'bal', 'beqz', 'bnez', 'beq', 'bne', 'blez', 'bgtz', 'bltz', 'bgez', 'bltzal', 'bgezal', 'j', 'jal', 'jr', 'jalr'}
def regs(ops): return re.findall(r'\$(\w+)', ops)
def reads(op, ops):
    r = regs(ops)
    if op in ('lui', 'mfhi', 'mflo', 'mfc0', 'j', 'jal'): return []
    if op in LOADS: return r[1:] + ([r[0]] if op in ('lwl', 'lwr') else [])
    if op in ('sb', 'sh', 'sw', 'swl', 'swr', 'beq', 'bne', 'jr', 'mtc0', 'mthi', 'mtlo', 'mult', 'multu', 'div', 'divu') or op in BR: return r
    if op == 'move': return r[1:]
    return r[1:]
def target(op, ops):
    m = re.search(r'0x([0-9a-f]+)\s*$', ops)
    return int(m.group(1), 16) if m and op in BR - {'jr', 'jalr'} else None
bad = 0
for i, a in enumerate(order):
    op, ops = ins[a]
    if op in LOADS:
        d = regs(ops)[0]
        if d in ('zero', '0'): continue
        nexts = []
        if i + 1 < len(order): nexts.append(order[i + 1])
        if i > 0 and ins[order[i - 1]][0] in BR:       # load in a delay slot
            t = target(*ins[order[i - 1]])
            if t is not None and t in ins: nexts.append(t)
        for n in nexts:
            nop, nops = ins[n]
            if nop in ('lwl', 'lwr') and op in ('lwl', 'lwr'): continue
            if d in reads(nop, nops):
                print('load-delay hazard at %08x: %s %s -> %08x: %s %s' % (a, op, ops, n, nop, nops)); bad += 1
    if op in ('mflo', 'mfhi'):
        for n in order[i + 1:i + 3]:
            if ins[n][0] in ('mult', 'multu', 'div', 'divu'):
                print('HI/LO hazard at %08x' % a); bad += 1
print('hazards:', bad, 'in', len(order), 'instructions')
sys.exit(1 if bad else 0)
