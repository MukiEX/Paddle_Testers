# Saturn Controller Test

A bare-metal Sega Saturn program that shows what each controller port is reporting.
Boot `Saturn Controller Test.cue` (in [`../releases/`](../releases/)) in an emulator or from an optical drive emulator.

- **Top:** a pad diagram for Player 1 and Player 2. Buttons light up as they're pressed (d-pad, A/B/C, X/Y/Z, L/R, START). Above each pad: the peripheral ID and name (digital pad, 3D pad analog, racing wheel, mission stick, Shuttle Mouse, keyboard, not connected). Below it:
  - **RAW:** the report bytes as the SMPC returned them, up to 6.
  - **BOTH:** frames where LEFT+RIGHT, UP+DOWN, and Y+Z were held at the same time.
- **Spinner view:** once a port is detected as a JP3 spinner (rules below), its diagram becomes a pad with a knob in place of the d-pad, and a white marker on the knurled rim turns one segment per edge (16 per turn of the marker). The name shows the wiring (`JP3 SPINNER L/R`, `Y/Z` or `D-PAD`) and the BOTH line becomes **SPIN** (running edge total) and **STEP** (edges this frame).
- **Bottom:** a bit stream of LEFT, RIGHT, UP, DOWN, Y and Z for both ports, one pixel column per frame (an oscilloscope-style sweep, about 4.4 seconds across). Red: both lines of a pair held in that frame. Orange: the pad dropped out (no device reported) after having been connected.

A+B+C+START clears that port's BOTH counters and SPIN total.

## Spinner detection (same rules as the Saturn Paddle Edition)

| Wiring | Latches when |
|---|---|
| LEFT = phase A, RIGHT = phase B (USB-to-Saturn adapters) | LEFT and RIGHT read held together |
| Y = phase A, Z = phase B | Y and Z read held together |
| Across the d-pad pairs: LEFT or RIGHT = A, UP or DOWN = B (an encoder inside a real pad) | two frame-perfect flips between A-only and B-only within 60 frames (a quick spin) |

A real Saturn pad drops off the bus while LEFT+RIGHT or UP+DOWN are held (the console reads its ID from those lines OR'd in pairs), which is why an encoder inside a pad has to go across the pairs; those drop-outs show as orange columns. Any ID change, including a drop-out, resets the port's detection, as in the patch. Decoding: phase = A xor 3B; a change of 2 in one frame counts as two edges in the last direction.

## Notes

- 320×224, 60 Hz. The pads are read with SMPC INTBACK once per frame (peripheral data only, 15-byte mode, acquisition-time optimisation on), the same read the console's games get; the result is drawn at the next VBlank.
- Pad-type devices (ID type 0 or 1: digital pad, 3D pad, wheel, mission stick) light the diagram from their first two report bytes. Other devices (mouse, keyboard) only show the ID and raw bytes.
- The disc boots with Jo Engine's `IP.BIN` (all regions, JTUE). Like any homebrew disc it runs in emulators and from optical drive emulators; a burned CD-R needs a modchip.
- No SDK: VDP2 shows one 512×256 8-bit bitmap layer; every button has its own palette entry, so lighting a button is a colour RAM write.
- Tested in Yabause only so far, not on real hardware.

## Building

Needs SH binutils (`sh-elf-as`, `sh-elf-objcopy`; no compiler or linker), Python 3 with Pillow, and the X11 `koi6x10` / `koi6x13b` PCF fonts (xfonts-cyrillic; public domain misc-fixed).

```sh
./build.sh          # -> build/0.BIN, build/Saturn Controller Test.bin/.cue (zip it into ../releases/)
```

Set `SH_PREFIX` if your binutils aren't `sh-elf-*`. `tools/gen.py` draws the background, palette, font and bit-stream patterns; `tools/mkdisc.py` writes the ISO 9660 image as MODE1/2352 with EDC/ECC.

`test/ctest.py` runs scripted checks in the libretro Yabause core with the debug hooks from [`third_party/`](third_party/) (set `YAB_CORE`): one column per frame, both-held counters, counter reset, normal d-pad use not latching, the d-pad (cross) and Y/Z spinners latching and counting both ways, drop-out flagging, plus screenshots with a pad, spinners, a 3D pad and a mouse.
