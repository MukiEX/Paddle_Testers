# Paddle Testers

Controller test programs for checking paddle, spinner and mouse-style controllers on retro consoles. Each one shows a live diagram per player plus the signals the matching Paddle Edition patch reads.

| Folder | Platform | Image |
|---|---|---|
| [`ps1/`](ps1/) | PlayStation | BIN/CUE: pad, DualShock, PS Mouse, NeGcon, Namco Volume, JP3 spinner on the d-pad |
| [`saturn/`](saturn/) | Sega Saturn | BIN/CUE: two pad diagrams, IDs and raw bytes for any device, LEFT/RIGHT/Y/Z bit streams for JP3 wiring checks |
| [`neogeo/`](neogeo/) | Neo Geo (MVS/AES) | `.neo` cart: both pads with START/SELECT/COIN, JP3 L/R encoder, Pop 'n Bounce 7-bit dial |

Each folder builds on its own; see its README.
