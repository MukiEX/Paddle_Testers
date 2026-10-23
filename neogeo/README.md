# Neo Geo Controller Test

An unencrypted Neo Geo cartridge (`.neo`) that shows what each controller port
is reporting. Unzip `Neo Geo Controller Test.zip` from [`releases/`](../releases/)
and load the `.neo` in MiSTer's Neo Geo core or any emulator that takes `.neo`
files.

- **Top:** a Neo Geo CD-style pad for Player 1 and Player 2.
  - The d-pad, A B C D, START, SELECT and COIN light up as they're pressed.
  - The `INPUT` row under each pad shows the raw `UDLRABCD` bits.
- **Bottom:** a spinner detector per port, for either kind of spinner the
  Paddle Edition patches understand:
  - **JP3 encoder** (Taito F3 style), on LEFT/RIGHT or across the d-pad pairs.
    The heading shows which wiring was seen (`L/R` or `PAIRS`). Shows the count, the speed in counts
    per second, and SKIP, the samples where both lines changed at once.
  - **7-bit dial** (Pop 'n Bounce style): shows the position (0–127) and the
    summed count.

## Detection

Both ports are sampled about 3,900 times a second from the LSPC raster timer
(IRQ2), so fast spins are counted exactly.

| Signal | Shown as |
|---|---|
| LEFT = phase A, RIGHT = phase B; A leading B = clockwise = +1 | JP3 ENCODER `L/R` `DETECTED` after 12 clean steps (only LEFT/RIGHT changed), as long as clean steps outnumber other changes and skips 4 to 1 |
| LEFT or RIGHT = phase A, UP or DOWN = phase B (an encoder inside a real pad) | JP3 ENCODER `PAIRS` `DETECTED` after a quick spin: 12 steps the same way, each within 120 samples (about 30 ms), the same rule as the Paddle Edition patches. A thumb on a d-pad can't do that. Shown only when L/R wasn't seen |
| Bits 0–6 as a position that moves 1–3 at a time | 7-BIT DIAL `DETECTED` after 8 such steps in a row in the same direction, which no pad can produce |

`DETECTED` stays on once seen. `MOVING` shows for half a second after each step.
In dial mode the pad diagram flickers, because the position uses the button lines.

## Notes

- The BIOS's own startup runs as usual, then the program takes over and never
  hands control back. There's no eye-catcher and no sound.
- The Z80 program only echoes the BIOS's commands.
- NGH `0420`. That avoids every number MiSTer or Geolith treats specially;
  V-Liner's `0999`, for example, disables player 2 in Geolith.
- Tested in Geolith in MVS mode.

## Building

Needs `vasmm68k_mot`, `vasmz80_oldstyle` (vasm with `CPU=z80 SYNTAX=oldstyle`)
and Python 3 with numpy.

```sh
./build.sh          # -> build/padtest.neo (the release zip holds it renamed)
```

- `tools/mkgfx.py` draws the pad art and the 5×7 font into the S ROM.
- `src/padtest.asm` is the 68000 program.
- `src/m1.z80` is the Z80 program.
- `tools/mkneo.py` packs everything into the `.neo`.

`test/t_io.py` runs scripted checks: both pads, P1 encoder +300/−100, and P2 dial.
