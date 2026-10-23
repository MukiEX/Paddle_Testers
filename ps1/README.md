# PS1 Controller Test

A bare-metal PlayStation program that shows what each controller port is reporting.
Boot `PS1 Controller Test.cue` (in [`releases/`](releases/)) in an emulator or from an optical drive emulator.

- **Top:** a live diagram for Player 1 and Player 2. Buttons light up as they're pressed; the NeGcon's halves twist, the Volume's knob turns, a JP3 spinner's wheel spins, analog sticks move.
- **Bottom:** an X-axis bar per player:
  - Mouse: fills from the centre with this frame's X counts; the white marker is the running X total (wraps every 256 counts).
  - Namco Volume: fills from the left with the knob value (0–255).
  - NeGcon: twist, filled from the centre.
  - JP3 spinner (either wiring): edges this frame; the marker is the running edge total.
  - Analog pad: left stick X.
  - Digital pad: LEFT/RIGHT.
- **Raw line:** the controller ID and the report bytes, in red while reads are failing.

## Detection (same rules as the MD3 Paddle Edition)

| Report | Shown as |
|---|---|
| ID `12` | PS Mouse |
| ID `23` | Namco Volume, until NeGcon-only input (I, II or L past `60`, or any button other than START/CIRCLE) shows on 3 reads in a row; then NeGcon until unplugged. `NEGCON? n` counts those reads. |
| Anything else | Controller; becomes a JP3 spinner wired one of two ways. **JP3 SPINNER**: LEFT = phase A, RIGHT = phase B (adapters), latched the first time LEFT and RIGHT read pressed together. **JP3 PAIRS**: across the d-pad pairs, A = LEFT or RIGHT, B = UP or DOWN (an encoder inside a real pad), latched when the pad goes straight from only LEFT/RIGHT to only UP/DOWN (or back) between two reads twice within a second; a thumb always passes a diagonal or the centre. |
| Failed read | The last good read is kept; 30 failures in a row = NOT CONNECTED |
| ID `23` with I, II and L all ≥ `F0` | Garbled; treated as a failed read |

Volume buttons: A is on the START bit, B on the CIRCLE bit.

## Notes

- Output is 320×240 at 60 Hz (NTSC) on every console.
- The disc has no licence sectors, so it boots in emulators and optical drive emulators but needs a modchip for a burned disc.
- No SDK or BIOS calls after boot: SIO0 is polled directly once per frame and the GPU is driven through GP0/GP1.

## Building

Needs clang/lld 18 or newer (MIPS I target), Python 3 with Pillow, and the X11 `koi6x9` / `koi8x16b` PCF fonts (xfonts-cyrillic; public domain misc-fixed).

```sh
./build.sh          # -> build/PADTEST.EXE, build/PS1 Controller Test.bin/.cue
```

`tools/hazards_elf.py` fails the build if the compiled code has an R3000 load-delay or HI/LO hazard. LLVM's MIPS I mode handles load delays itself; `tools/fixhilo.py` pads MFLO/MFHI.

`test/ctest.py` runs scripted checks in PCSX-ReARMed through libretro (set `PCSX_CORE`): pad buttons, JP3 counting both ways in both wirings (and a rolled d-pad not latching), mouse counts and buttons, Volume → NeGcon switching, empty port.
