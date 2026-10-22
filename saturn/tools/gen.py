#!/usr/bin/env python3
"""Generate data blobs for the Saturn controller tester (written to ../build).

Outputs (in build/):
  bg.bin     512x224 8bpp background bitmap (VDP2 NBG0 layout, row stride 512)
  pal.bin    256 x RGB555 colour RAM words
  font.bin   96 glyphs x 16 bytes (rows 0..12 used, bit7 = leftmost of 6 px)
  pats.bin   bit-stream column patterns: 8 traces x 3 states x 12 bytes
  btncol.bin 13 buttons x (fillOff, fillOn, labelOff, labelOn) RGB555 words
  preview.png
"""
import gzip, io, os, struct
from PIL import PcfFontFile, ImageFont, Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, '..', 'build'); os.makedirs(OUT, exist_ok=True)

def pcf(name):
    pil = os.path.join(OUT, name + '.pil')
    if not os.path.exists(pil):
        p = PcfFontFile.PcfFontFile(io.BytesIO(gzip.open('/usr/share/fonts/X11/cyrillic/%s.pcf.gz' % name).read()))
        p.save(os.path.join(OUT, name))
    return ImageFont.load(pil)

F13 = pcf('koi6x13b'); F10 = pcf('koi6x10')
BIG = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 9)

W, H = 512, 224
# ---------------------------------------------------------------- palette
def rgb(r, g, b): return ((b >> 3) << 10) | ((g >> 3) << 5) | (r >> 3)
pal = [0] * 256
BG, BODY, EDGE, TEXT, DIM, BASE, CURSOR, GRID = range(8)
pal[BG] = rgb(14, 16, 30); pal[BODY] = rgb(58, 60, 72); pal[EDGE] = rgb(22, 22, 28)
pal[TEXT] = rgb(235, 235, 240); pal[DIM] = rgb(130, 135, 155); pal[BASE] = rgb(70, 74, 100)
pal[CURSOR] = rgb(255, 255, 255); pal[GRID] = rgb(40, 44, 66)
TRACE_COL = [rgb(60, 200, 255), rgb(255, 210, 40), rgb(80, 230, 110), rgb(240, 90, 240)]
for i, c in enumerate(TRACE_COL): pal[8 + i] = c
RED = 12; pal[RED] = rgb(255, 40, 40)
DPADC = 13; pal[DPADC] = rgb(36, 36, 44)

# button order = SMPC/SGL bit 15..3
BTN = ['RIGHT', 'LEFT', 'DOWN', 'UP', 'START', 'A', 'C', 'B', 'R', 'X', 'Y', 'Z', 'L']
def fill_idx(p, b): return 32 + p * 16 + b
def lab_idx(p, b): return 64 + p * 16 + b
btncol = []
for b in BTN:
    if b in ('RIGHT', 'LEFT', 'DOWN', 'UP'): off, on = rgb(80, 82, 96), rgb(60, 200, 255)
    elif b == 'START': off, on = rgb(95, 95, 110), rgb(255, 255, 255)
    elif b in ('A', 'B', 'C'): off, on = rgb(92, 92, 108), rgb(255, 150, 30)
    elif b in ('X', 'Y', 'Z'): off, on = rgb(92, 92, 108), rgb(80, 230, 110)
    else: off, on = rgb(88, 88, 104), rgb(240, 90, 240)
    btncol.append((off, on, rgb(210, 210, 220), rgb(0, 0, 0)))
for p in range(2):
    for i, (off, on, lo, ln) in enumerate(btncol):
        pal[fill_idx(p, i)] = off; pal[lab_idx(p, i)] = lo

# ---------------------------------------------------------------- background
img = Image.new('P', (W, H), BG)
d = ImageDraw.Draw(img)

def text(x, y, s, col=TEXT, font=F13):
    d.text((x, y), s, font=font, fill=col)

def label_center(cx, cy, s, col, font=BIG):
    # 1-colour (no AA) label centred on (cx, cy)
    m = Image.new('L', (40, 20), 0); dm = ImageDraw.Draw(m)
    dm.fontmode = '1'
    dm.text((20, 10), s, font=font, fill=255, anchor='mm')
    bb = m.getbbox()
    if not bb: return
    gw, gh = bb[2] - bb[0], bb[3] - bb[1]
    ox, oy = cx - gw // 2 - bb[0], cy - gh // 2 - bb[1]
    for y in range(bb[1], bb[3]):
        for x in range(bb[0], bb[2]):
            if m.getpixel((x, y)) > 127: img.putpixel((ox + x, oy + y), col)

layout = {}   # for the readme / tests
for p in range(2):
    x0 = p * 160
    text(x0 + 4, 2, 'P%d' % (p + 1), TEXT)
    # shoulders
    d.rounded_rectangle((x0 + 14, 18, x0 + 56, 34), 6, fill=fill_idx(p, BTN.index('L')), outline=EDGE)
    d.rounded_rectangle((x0 + 104, 18, x0 + 146, 34), 6, fill=fill_idx(p, BTN.index('R')), outline=EDGE)
    label_center(x0 + 35, 23, 'L', lab_idx(p, BTN.index('L')))
    label_center(x0 + 125, 23, 'R', lab_idx(p, BTN.index('R')))
    # body: two grips + bridge
    d.ellipse((x0 + 6, 27, x0 + 72, 87), fill=BODY, outline=EDGE)
    d.ellipse((x0 + 88, 27, x0 + 154, 87), fill=BODY, outline=EDGE)
    d.rectangle((x0 + 38, 28, x0 + 122, 78), fill=BODY)
    d.line((x0 + 38, 27, x0 + 122, 27), fill=EDGE)
    d.arc((x0 + 40, 60, x0 + 120, 100), 200, 340, fill=EDGE)
    d.rectangle((x0 + 50, 74, x0 + 110, 79), fill=BODY)
    # d-pad
    cx, cy, a, l = x0 + 39, 57, 7, 19
    d.rectangle((cx - a - 1, cy - l - 1, cx + a + 1, cy + l + 1), fill=EDGE)
    d.rectangle((cx - l - 1, cy - a - 1, cx + l + 1, cy + a + 1), fill=EDGE)
    d.rectangle((cx - a, cy - l, cx + a, cy - a - 1), fill=fill_idx(p, BTN.index('UP')))
    d.rectangle((cx - a, cy + a + 1, cx + a, cy + l), fill=fill_idx(p, BTN.index('DOWN')))
    d.rectangle((cx - l, cy - a, cx - a - 1, cy + a), fill=fill_idx(p, BTN.index('LEFT')))
    d.rectangle((cx + a + 1, cy - a, cx + l, cy + a), fill=fill_idx(p, BTN.index('RIGHT')))
    d.rectangle((cx - a, cy - a, cx + a, cy + a), fill=DPADC)
    t = 4
    d.polygon([(cx, cy - l + 3), (cx - t, cy - l + 3 + t), (cx + t, cy - l + 3 + t)], fill=lab_idx(p, BTN.index('UP')))
    d.polygon([(cx, cy + l - 3), (cx - t, cy + l - 3 - t), (cx + t, cy + l - 3 - t)], fill=lab_idx(p, BTN.index('DOWN')))
    d.polygon([(cx - l + 3, cy), (cx - l + 3 + t, cy - t), (cx - l + 3 + t, cy + t)], fill=lab_idx(p, BTN.index('LEFT')))
    d.polygon([(cx + l - 3, cy), (cx + l - 3 - t, cy - t), (cx + l - 3 - t, cy + t)], fill=lab_idx(p, BTN.index('RIGHT')))
    # start
    d.rounded_rectangle((x0 + 70, 62, x0 + 90, 70), 4, fill=fill_idx(p, BTN.index('START')), outline=EDGE)
    text(x0 + 66, 72, 'START', DIM, F10)
    # face buttons: XYZ top row (small), ABC bottom row (big)
    for name, bx, by, r in (('X', 100, 44, 7), ('Y', 118, 39, 7), ('Z', 136, 44, 7),
                            ('A', 102, 64, 9), ('B', 121, 58, 9), ('C', 140, 64, 9)):
        bi = BTN.index(name)
        d.ellipse((x0 + bx - r, by - r, x0 + bx + r, by + r), fill=fill_idx(p, bi), outline=EDGE)
        label_center(x0 + bx, by, name, lab_idx(p, bi))
    text(x0 + 4, 89, 'RAW', DIM)
    text(x0 + 4, 101, 'BOTH', DIM)
d.line((159, 0, 159, 111), fill=GRID)
d.line((0, 113, 319, 113), fill=GRID)
text(4, 114, 'BIT STREAM', TEXT, F10)
text(84, 114, '1px = 1 frame, red = both held', DIM, F10)
TX0, TW, TY0 = 52, 264, 126
names = ['LEFT', 'RIGHT', 'Y', 'Z']
for i in range(8):
    p, t = divmod(i, 4)
    y = TY0 + i * 12
    text(2, y + 1, '%d %s' % (p + 1, names[t]), 8 + t, F10)
    d.line((TX0, y + 9, TX0 + TW - 1, y + 9), fill=BASE)
    if t == 3 and p == 0: d.line((0, y + 11, 319, y + 11), fill=GRID)
img.putpalette(sum([[((c & 31) << 3), (((c >> 5) & 31) << 3), (((c >> 10) & 31) << 3)] for c in pal], []))
img.save(os.path.join(OUT, 'preview.png'))
open(os.path.join(OUT, 'bg.bin'), 'wb').write(img.tobytes())
open(os.path.join(OUT, 'pal.bin'), 'wb').write(struct.pack('>256H', *pal))
open(os.path.join(OUT, 'btncol.bin'), 'wb').write(b''.join(struct.pack('>4H', *c) for c in btncol))

# ---------------------------------------------------------------- font (6x13 bold)
font = bytearray()
for c in range(32, 128):
    m = Image.new('L', (8, 16), 0); ImageDraw.Draw(m).text((0, 0), chr(c), font=F13, fill=255)
    g = bytearray(16)
    for y in range(13):
        v = 0
        for x in range(6):
            if m.getpixel((x, y)): v |= 0x80 >> x
        g[y] = v
    font += g
open(os.path.join(OUT, 'font.bin'), 'wb').write(font)

# ---------------------------------------------------------------- trace patterns
pats = bytearray()
for i in range(8):
    p, t = divmod(i, 4)
    for state in range(3):
        col = [BG] * 12
        if state == 0: col[9] = BASE
        else:
            for y in range(2, 10): col[y] = 8 + t if state == 1 else RED
        if t == 3 and p == 0: col[11] = GRID
        pats += bytes(col)
open(os.path.join(OUT, 'pats.bin'), 'wb').write(pats)

consts = dict(TX0=TX0, TW=TW, TY0=TY0, CURSOR=CURSOR, TEXT=TEXT, BG=BG)
open(os.path.join(OUT, 'consts.inc'), 'w').write(''.join('.equ %s, %d\n' % kv for kv in consts.items()))
print('ok', len(font), len(pats))
