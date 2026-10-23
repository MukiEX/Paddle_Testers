"""Scripted check in Geolith through libretro (see test/README.md).

Presses buttons on both pads, spins a JP3 encoder on P1 (+300 then -100),
turns a 7-bit dial on P2 (+120), then spins an encoder wired across P2's
d-pad pairs (A = LEFT, B = UP), and saves a contact sheet to build/t_io.png.
"""
import os, sys
import neo, util

here = os.path.dirname(os.path.abspath(__file__))
ROM = os.path.join(here, '..', 'build', 'padtest.neo')
n = neo.Neo(ROM, system=sys.argv[1] if len(sys.argv) > 1 else 'mvs')
n.run(400)
F = util.Film()
F.add(n, 'idle')
n.press(0, 'UP', 'A', 'C'); n.press(1, 'RIGHT', 'B', 'D', 'START'); n.run(3)
F.add(n, 'P1 UP A C / P2 RIGHT B D START')
n.release(0, 'UP', 'A', 'C'); n.release(1, 'RIGHT', 'B', 'D', 'START')
n.press(0, 'SELECT'); n.run(3); F.add(n, 'coin'); n.release(0, 'SELECT')
n.spinner(0, True, quantum_us=1000)
n.spin_counts(0, 300, rate=600); n.run(40); F.add(n, 'P1 encoder +300')
n.spin_counts(0, -100, rate=900); n.run(20); F.add(n, 'P1 encoder -100')
assert n.r16(0x100042) == 200, 'P1 encoder count'
NAMES = ['UP', 'DOWN', 'LEFT', 'RIGHT', 'A', 'B', 'C', 'D']
pos = 0
for f in range(60):
    pos = (pos + 2) & 0x7f
    n.held[1].clear()
    for b in range(7):
        if pos >> b & 1:
            n.held[1].add(neo.BTN[NAMES[b]])
    n.run(1)
F.add(n, 'P2 dial +120')
assert n.r8(0x10008b) and not n.r8(0x10008a), 'P2 seen as a dial, not an encoder'
assert not n.r8(0x1000a7) and not n.r8(0x100067), 'no pairs wiring seen on the dial or the L/R encoder'
n.held[1].clear(); n.run(10)
n.spinner(1, True, quantum_us=1000, wiring='pairs')
n.spin_counts(1, 40, rate=300); n.run(10)
c0 = n.r16(0x1000a2)
n.spin_counts(1, -100, rate=600); n.run(20)
F.add(n, 'P2 pairs encoder')
assert n.r8(0x1000a7), 'P2 pairs wiring recognised'
assert (n.r16(0x1000a2) - c0) & 0xffff == 0x10000 - 100, 'P2 pairs count -100'
F.save(os.path.join(here, '..', 'build', 't_io.png'), cols=2)
print('ok')
