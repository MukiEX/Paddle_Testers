# Paddle Testers

Controller test programs for checking paddle, spinner and mouse-style controllers on retro consoles. Each one shows a live diagram per player plus the signals the matching Paddle Edition patch reads.

| Folder | Platform | Image |
|---|---|---|
| [`ps1/`](ps1/) | PlayStation | BIN/CUE: pad, DualShock, PS Mouse, NeGcon, Namco Volume, JP3 spinner on the d-pad |
| [`saturn/`](saturn/) | Sega Saturn | BIN/CUE: two pad diagrams, IDs and raw bytes for any device, JP3 spinner detection (L/R, Y/Z, encoder across the d-pad) with a knob view, LEFT/RIGHT/UP/DOWN/Y/Z bit streams with pad drop-outs |
| [`neogeo/`](neogeo/) | Neo Geo (MVS/AES) | `.neo` cart: both pads with START/SELECT/COIN, JP3 encoder (LEFT/RIGHT or across the d-pad pairs), Pop 'n Bounce 7-bit dial |

Each folder builds on its own; see its README.
