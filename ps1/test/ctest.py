"""Scripted checks: each scenario boots with given port devices, drives input and
reads the program's port state from RAM (struct layout from main.c)."""
import sys, os, subprocess
from env import ROOT
from retro import *
cue = os.path.join(ROOT, 'build', 'PS1 Controller Test.cue')
nm = subprocess.run(['llvm-nm', os.path.join(ROOT, 'build', 'padtest.elf')], capture_output=True, text=True).stdout
sym = {l.split()[2]: int(l.split()[0], 16) for l in nm.splitlines() if len(l.split()) == 3}
PORT = sym['port']; SZ = 104
TN = ['NONE', 'PAD', 'MOUSE', 'NEGCON', 'VOLUME', 'JP3']
def st(e, i):
    b = PORT + i * SZ
    s8 = lambda v: v - 256 if v > 127 else v
    s32 = lambda v: v - (1 << 32) if v >> 31 else v
    return dict(type=TN[e.r32(b + 44)], id=e.r8(b), btn=e.r16(b + 54), dx=s32(e.r32(b + 56)), xacc=s32(e.r32(b + 64)),
                step=s32(e.r32(b + 68)), raw=e.rb(b, 8).hex(), jp3=e.r8(b + 51), negn=e.r8(b + 49), bad=e.r32(b + 40), fails=e.r32(b + 92), reads=e.r32(b + 88))
fails = 0
def check(name, cond, info=''):
    global fails
    print(('ok   ' if cond else 'FAIL ') + name, info)
    if not cond: fails += 1
def shot(e, n): e.shot(os.path.join(ROOT, 'shots', n + '.png'))

# 1. pads: buttons and JP3
e = Emu(cue, ports=('standard', 'dualshock'))
e.run(120)
check('pad detected', st(e, 0)['type'] == 'PAD', st(e, 0))
# the emulator takes ~33 frames to attach a non-default device, so count failures from here on
f0 = (st(e, 0)['fails'], st(e, 1)['fails'])
e.pad[0] |= {B, X, L, UP}; e.run(4)
s = st(e, 0); check('buttons', s['btn'] == (0x0040 | 0x0010 | 0x0004 | 0x1000), hex(s['btn']))
e.analog[1] = [20000, -12000, 0, 0]; e.pad[1] |= {START}; e.run(4)
shot(e, 'pad_buttons'); s1 = st(e, 1); print('  port2', s1)
e.pad[0].clear(); e.analog[1] = [0, 0, 0, 0]; e.pad[1].clear(); e.run(2)
# quadrature: LEFT=A RIGHT=B; first L+R latches
seq = [{LEFT, RIGHT}, {RIGHT}, set(), {LEFT}, {LEFT, RIGHT}, {RIGHT}, set(), {LEFT}, {LEFT, RIGHT}]
for p in seq: e.pad[0] = set(p); e.run(1)
s = st(e, 0); check('JP3 latched', s['type'] == 'JP3', s)
check('JP3 counts one way', s['xacc'] == 8 or s['xacc'] == -8, s['xacc'])
x0 = s['xacc']
for p in reversed(seq[:-1]): e.pad[0] = set(p); e.run(1)
check('JP3 counts back', st(e, 0)['xacc'] == 0, st(e, 0)['xacc'])
for p in seq[:5]: e.pad[0] = set(p); e.run(1)
shot(e, 'jp3')
e.pad[0] = set(); e.run(2)

check('no read failures after settling', (st(e, 0)['fails'], st(e, 1)['fails']) == f0, ((st(e, 0)['fails'], st(e, 1)['fails']), f0))

# 1b. JP3 across the d-pad pairs (A = LEFT or RIGHT, B = UP or DOWN)
# (port 2 of the same session: the core only survives a few instances per process)
# a thumb rolling the d-pad round and round, 2 frames per position, and
# tapping centre <-> diagonal: must not latch
roll = [{UP}, {UP, RIGHT}, {RIGHT}, {RIGHT, DOWN}, {DOWN}, {DOWN, LEFT}, {LEFT}, {LEFT, UP}]
for k in range(48): e.pad[1] = set(roll[k % 8]); e.run(2)
for k in range(20): e.pad[1] = {UP, LEFT} if k % 2 else set(); e.run(1)
e.pad[1] = set(); e.run(2)
check('d-pad rolling does not latch', st(e, 1)['type'] == 'PAD', st(e, 1))
# one LEFT -> UP swap, then nothing for over a second, then one more: no latch
e.pad[1] = {LEFT}; e.run(1); e.pad[1] = {UP}; e.run(1); e.pad[1] = set(); e.run(70)
e.pad[1] = {LEFT}; e.run(1); e.pad[1] = {UP}; e.run(1); e.pad[1] = set(); e.run(2)
check('swaps more than a second apart do not latch', st(e, 1)['type'] == 'PAD', st(e, 1))
# encoder wired LEFT (A) / UP (B), spun fast: skips a state between reads
PP = [set(), {LEFT}, {LEFT, UP}, {UP}]
q = 1
e.pad[1] = PP[q]; e.run(1)
for k in range(3): q = (q + 2) % 4; e.pad[1] = PP[q]; e.run(1)
s = st(e, 1); check('fast spin latches pairs wiring', s['type'] == 'JP3' and s['jp3'] == 2, s)
x0 = s['xacc']
for k in range(8): q = (q + 1) % 4; e.pad[1] = PP[q]; e.run(2)
check('pairs: 8 edges one way', st(e, 1)['xacc'] - x0 == 8, st(e, 1)['xacc'] - x0)
for k in range(8): q = (q - 1) % 4; e.pad[1] = PP[q]; e.run(2)
check('pairs: and back', st(e, 1)['xacc'] == x0, st(e, 1)['xacc'])
# the other contacts of each pair work too (RIGHT for A, DOWN for B)
PR = [set(), {RIGHT}, {RIGHT, DOWN}, {DOWN}]
for k in range(4): q = (q + 1) % 4; e.pad[1] = PR[q]; e.run(2)
check('pairs: RIGHT/DOWN contacts count too', st(e, 1)['xacc'] - x0 == 4, st(e, 1)['xacc'] - x0)
shot(e, 'jp3_pairs')

# 2. mouse + NeGcon (no NeGcon-only input yet => Volume)
e = Emu(cue, ports=('mouse', 'negcon'))
e.run(120)
check('mouse detected', st(e, 0)['type'] == 'MOUSE', st(e, 0))
check('0x23 starts as Volume', st(e, 1)['type'] == 'VOLUME', st(e, 1))
tot = 0
for k in range(10):
    e.mouse[0][0] = 7; e.run(1); tot += 7
e.mouse[0][2] = 1; e.analog[1] = [-20000, 0, 0, 0]; e.pad[1] |= {START}; e.run(3)
s = st(e, 0); check('mouse X counts', s['xacc'] > 0, s); check('mouse left button', s['btn'] & 8, hex(s['btn']))
s1 = st(e, 1); print('  vol', s1); check('Volume A (START bit)', s1['btn'] & 0x0800, hex(s1['btn']))
shot(e, 'mouse_volume')
e.mouse[0][2] = 0; e.pad[1].clear()
# NeGcon-only input: d-pad UP for 2 reads (not enough), then 3+
e.pad[1] |= {UP}; e.run(2); e.pad[1].clear(); e.run(1)
check('2 reads of NeGcon input: still Volume', st(e, 1)['type'] == 'VOLUME', st(e, 1))
e.pad[1] |= {UP}; e.run(4); e.pad[1].clear(); e.run(1)
check('3 reads: NeGcon', st(e, 1)['type'] == 'NEGCON', st(e, 1))
e.analog[1] = [25000, 0, 0, 0]; e.pad[1] |= {B, A}; e.run(3)
shot(e, 'mouse_negcon'); print('  negcon', st(e, 1))
e.pad[1].clear(); e.analog[1] = [0, 0, 0, 0]

# 3. empty port
e = Emu(cue, ports=('standard', 'none'))
e.run(90)
check('empty port = none', st(e, 1)['type'] == 'NONE', st(e, 1))
shot(e, 'empty')
print('FAILURES:', fails); sys.exit(1 if fails else 0)
