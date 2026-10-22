# Saturn Controller Test

A bare-metal Sega Saturn program that shows what each controller port is reporting.
Boot `Saturn Controller Test.cue` (in [`releases/`](releases/)) in an emulator or from an optical drive emulator.

- **Top:** a pad diagram for Player 1 and Player 2. Buttons light up as they're pressed (d-pad, A/B/C, X/Y/Z, L/R, START). Above each pad: the peripheral ID and name (digital pad, 3D pad analog, racing wheel, mission stick, Shuttle Mouse, keyboard, not connected). Below it:
  - **RAW:** the report bytes as the SMPC returned them, up to 6.
  - **BOTH:** frames where LEFT+RIGHT, and Y+Z, were held at the same time.
- **Bottom:** a bit stream of LEFT, RIGHT, Y and Z for both ports, one pixel column per frame (an oscilloscope-style sweep, about 4.4 seconds across). Any frame where both lines of a pair are held is drawn in red.

Those four lines are the two JP3 spinner wirings the Saturn Paddle Edition understands (LEFT/RIGHT, or Y/Z for adapters that clean the d-pad). The stream shows whether an adapter really passes left+right together, how many frames each phase lasts, and where steps get merged or dropped.

A+B+C+START clears that port's BOTH counters.

## Notes

- 320×224, 60 Hz. The pads are read with SMPC INTBACK once per frame (peripheral data only, 15-byte mode, acquisition-time optimisation on), the same read the console's games get; the result is drawn at the next VBlank.
- Pad-type devices (ID type 0 or 1: digital pad, 3D pad, wheel, mission stick) light the diagram from their first two report bytes. Other devices (mouse, keyboard) only show the ID and raw bytes.
- The disc boots with Jo Engine's `IP.BIN` (all regions, JTUE). Like any homebrew disc it runs in emulators and from optical drive emulators; a burned CD-R needs a modchip.
- No SDK: VDP2 shows one 512×256 8-bit bitmap layer; every button has its own palette entry, so lighting a button is a colour RAM write.
- Tested in Yabause only so far, not on real hardware.

## Building

Needs SH binutils (`sh-elf-as`, `sh-elf-objcopy`; no compiler or linker), Python 3 with Pillow, and the X11 `koi6x10` / `koi6x13b` PCF fonts (xfonts-cyrillic; public domain misc-fixed).

```sh
./build.sh          # -> build/0.BIN, build/Saturn Controller Test.bin/.cue
```

Set `SH_PREFIX` if your binutils aren't `sh-elf-*`. `tools/gen.py` draws the background, palette, font and bit-stream patterns; `tools/mkdisc.py` writes the ISO 9660 image as MODE1/2352 with EDC/ECC.

`test/ctest.py` runs scripted checks in the libretro Yabause core with the debug hooks from [`third_party/`](third_party/) (set `YAB_CORE`): one column per frame, both-held counters, counter reset, plus screenshots with a pad, a 3D pad and a mouse.
