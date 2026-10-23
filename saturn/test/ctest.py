"""Scripted checks of the Saturn controller tester in Yabause (libretro core with the debug
hooks from third_party/; set YAB_CORE or put yabause_libretro.so in third_party/).
Run after ./build.sh. Screenshots go to shots/."""
import os, sys, subprocess
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
ROOT = os.path.join(HERE, '..'); B = os.path.join(ROOT, 'build'); SHOTS = os.path.join(ROOT, 'shots')
os.makedirs(SHOTS, exist_ok=True)
from retro import Retro, DEV_JOYPAD, DEV_3DPAD, DEV_MOUSE
SH = os.environ.get('SH_PREFIX', 'sh-elf-')
syms = {l.split()[-1]: int(l.split()[0], 16) for l in subprocess.check_output([SH + 'objdump', '-t', os.path.join(B, 'tester.o')]).decode().splitlines() if ' .text\t' in l}
ST = 0x06004000 + syms['state']           # +0 sweep column; per port p at +4+8p: LR, UD, YZ both-held frames
fails = []
def check(name, ok, info=''):
    print(('PASS ' if ok else 'FAIL ') + name, info); (None if ok else fails.append(name))

r = Retro(os.path.join(B, 'Saturn Controller Test.cue'))
r.run(200)
a = r.r16(ST); r.run(60); b = r.r16(ST)
check('one bit-stream column per frame', (b - a) % 264 == 60, (b - a) % 264)
r.ports[0].buttons = {'Y', 'Z'}; r.run(10); r.ports[0].buttons = set(); r.run(3)
check('Y+Z both-held frames counted', r.r16(ST + 8) == 10, r.r16(ST + 8))
r.ports[0].buttons = {'LEFT', 'RIGHT'}; r.run(10); r.ports[0].buttons = set(); r.run(3)
check('LEFT+RIGHT both-held frames counted', r.r16(ST + 4) == 10, r.r16(ST + 4))
r.ports[0].buttons = {'A', 'B', 'C', 'START'}; r.run(3); r.ports[0].buttons = set(); r.run(2)
check('A+B+C+START clears the counters', (r.r16(ST + 4), r.r16(ST + 6), r.r16(ST + 8)) == (0, 0, 0))
SP = 0x06004000 + syms['spin']           # per port: +0 latch, +8 edge total, +10 dropped out
s16 = lambda a: (r.r16(a) ^ 0x8000) - 0x8000
r.set_device(0, 0); r.run(3); r.set_device(0, DEV_JOYPAD); r.run(70)   # replug: the Y+Z/LEFT+RIGHT checks above latched port 1
r.ports[0].buttons = {'LEFT'}; r.run(3); r.ports[0].buttons = {'UP'}; r.run(3); r.ports[0].buttons = set(); r.run(3)
check('normal d-pad use does not latch a spinner', r.r8(SP) == 0, r.r8(SP))
for b, n in (({'LEFT'}, 2), ({'UP'}, 1), ({'LEFT'}, 2)): r.ports[0].buttons = b; r.run(n)
check('two quick LEFT<->UP flips latch the d-pad spinner', r.r8(SP) == 3, r.r8(SP))
seq = [set(), {'LEFT'}, {'LEFT', 'UP'}, {'UP'}]; ph = 1; e0 = s16(SP + 8)
for i in range(10): ph = (ph + 1) % 4; r.ports[0].buttons = seq[ph]; r.run(2)
for i in range(4): ph = (ph - 1) % 4; r.ports[0].buttons = seq[ph]; r.run(2)
check('d-pad spinner counts edges both ways', s16(SP + 8) - e0 == 6, s16(SP + 8) - e0)
seq = [set(), {'Y'}, {'Y', 'Z'}, {'Z'}]; r.ports[1].buttons = seq[2]; r.run(2); ph = 2
for i in range(6): ph = (ph - 1) % 4; r.ports[1].buttons = seq[ph]; r.run(2)
check('Y/Z spinner latches on port 2 and counts', (r.r8(SP + 16), s16(SP + 24)) == (2, -6), (r.r8(SP + 16), s16(SP + 24)))
r.run(10); r.screenshot(os.path.join(SHOTS, 'spinners.png'))
r.set_device(1, 0); r.run(3)
check('a port that drops out is flagged and its spinner reset', (r.r8(SP + 26), r.r8(SP + 16)) == (1, 0), (r.r8(SP + 26), r.r8(SP + 16)))
r.set_device(1, DEV_JOYPAD); r.run(10)
r.ports[0].buttons = set(); r.ports[1].buttons = set(); r.run(3)
r.ports[0].buttons = {'LEFT', 'A', 'Y'}; r.ports[1].buttons = {'R', 'START'}; r.run(10)
r.screenshot(os.path.join(SHOTS, 'pads.png'))
r.set_device(1, DEV_3DPAD); r.ports[1].buttons = {'C', 'DOWN'}; r.ports[1].ax = 12000; r.run(30)
r.screenshot(os.path.join(SHOTS, '3dpad.png'))
r.set_device(1, DEV_MOUSE); r.ports[1].buttons = set(); r.run(30)
r.screenshot(os.path.join(SHOTS, 'mouse.png'))
print('\n%d failures' % len(fails), fails)
sys.exit(1 if fails else 0)
