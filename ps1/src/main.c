/* PS1 Controller Test
 *
 * Bare-metal PlayStation program: no SDK, no BIOS calls after boot.
 * Reads both controller ports directly through SIO0 once per frame and draws
 * a live diagram per player plus an X-axis bar at the bottom.
 *
 * Controller detection follows the Magical Drop III Paddle Edition rules:
 *   ID 0x12            PlayStation Mouse
 *   ID 0x23            Namco Volume, until NeGcon-only input (I, II or L past
 *                      0x60, or any button other than START/CIRCLE) shows on
 *                      3 reads in a row; then NeGcon until unplugged
 *   anything else      Controller; becomes a JP3 spinner (LEFT = phase A,
 *                      RIGHT = phase B) the first time LEFT and RIGHT read
 *                      pressed together
 *   failed read        repeat the last good read; 30 in a row = unplugged
 *   I, II, L >= 0xF0   on an 0x23 read = garbled, counts as a failed read
 */
typedef unsigned char u8; typedef signed char s8;
typedef unsigned short u16; typedef short s16;
typedef unsigned int u32; typedef int s32;

#define R32(a) (*(volatile u32 *)(a))
#define R16(a) (*(volatile u16 *)(a))
#define R8(a)  (*(volatile u8 *)(a))
#define GP0      R32(0x1F801810)
#define GP1      R32(0x1F801814)
#define GPUSTAT  R32(0x1F801814)
#define I_STAT   R32(0x1F801070)
#define I_MASK   R32(0x1F801074)
#define DPCR     R32(0x1F8010F0)
#define D2_MADR  R32(0x1F8010A0)
#define D2_BCR   R32(0x1F8010A4)
#define D2_CHCR  R32(0x1F8010A8)
#define JOY_DATA R8(0x1F801040)
#define JOY_STAT R32(0x1F801044)
#define JOY_MODE R16(0x1F801048)
#define JOY_CTRL R16(0x1F80104A)
#define JOY_BAUD R16(0x1F80104E)

#include "gen.h"

void *memset(void *d, int c, unsigned n) { u8 *p = d; while (n--) *p++ = (u8)c; return d; }
void *memcpy(void *d, const void *s, unsigned n) { u8 *p = d; const u8 *q = s; while (n--) *p++ = *q++; return d; }

static void delay(int n) { for (volatile int i = 0; i < n; i++) ; }

/* ------------------------------------------------------------------ GPU */
#define FW 320
#define FH 240
#define RGB(r, g, b) ((u32)(r) | ((u32)(g) << 8) | ((u32)(b) << 16))
#define XY(x, y) ((((u32)(y)) << 16) | (((u32)(x)) & 0xFFFF))
#define FONT_X 640
#define CLUT_X 640
#define CLUT_Y 480
#define CLUT_ID ((CLUT_Y << 6) | (CLUT_X >> 4))

/* palette */
#define C_BG     RGB(14, 16, 34)
#define C_PANEL  RGB(26, 30, 56)
#define C_LINE   RGB(58, 64, 102)
#define C_BODY   RGB(92, 98, 128)
#define C_BODY2  RGB(70, 76, 104)
#define C_OFF    RGB(40, 44, 70)
#define C_LIT    RGB(255, 226, 90)
#define C_TEXT   RGB(128, 128, 128)   /* texture modulation: 128 = as drawn */
#define C_DIM    RGB(80, 84, 110)
#define C_ACC    RGB(110, 190, 255)
#define C_TRI    RGB(64, 230, 150)
#define C_CIR    RGB(255, 90, 100)
#define C_CRO    RGB(110, 160, 255)
#define C_SQU    RGB(255, 130, 210)
#define C_FILL   RGB(80, 200, 255)
#define C_MARK   RGB(255, 255, 255)

static int db;   /* buffer being drawn: 0 = y 0, 1 = y 256 */

static void gwait(void) { while (!(GPUSTAT & 0x04000000)) ; }

static void upload(const void *src, int x, int y, int w, int h)   /* w in halfwords */
{
    int words = (w * h + 1) / 2;
    gwait();
    GP0 = 0x01000000;                       /* clear cache */
    GP0 = 0xA0000000; GP0 = XY(x, y); GP0 = ((u32)h << 16) | (u32)w;
    if (words % 16 == 0) {
        GP1 = 0x04000002;                   /* DMA direction CPU -> GP0 */
        DPCR |= 0x800;
        D2_MADR = (u32)src;
        D2_BCR = ((u32)(words / 16) << 16) | 16;
        D2_CHCR = 0x01000201;
        while (D2_CHCR & 0x01000000) ;
        GP1 = 0x04000000;
    } else {
        const u32 *p = src;
        while (words--) { while (!(GPUSTAT & 0x04000000)) ; GP0 = *p++; }
    }
    gwait();
}

static const u16 clut[16] = { 0x0000, 0x7FFF };

static void gpu_init(void)
{
    GP1 = 0x00000000;                       /* reset */
    GP1 = 0x06000000 | 0x260 | (0xC60 << 12);/* horizontal range */
    GP1 = 0x07000000 | 16 | (256 << 10);    /* vertical range: 240 lines */
    GP1 = 0x08000001;                       /* 320x240, NTSC, 15-bit */
    GP1 = 0x05000000;
    upload(font_tex, FONT_X, 0, 32, 192);
    upload(clut, CLUT_X, CLUT_Y, 16, 1);
}

static void begin_frame(void)
{
    int y = db ? 256 : 0;
    gwait();
    GP0 = 0xE1000000 | (FONT_X / 64) | (1 << 10);   /* tpage, 4-bit */
    GP0 = 0xE3000000 | ((u32)y << 10);
    GP0 = 0xE4000000 | (FW - 1) | ((u32)(y + FH - 1) << 10);
    GP0 = 0xE5000000 | ((u32)y << 11);
    GP0 = 0xE6000000;
    gwait();
    GP0 = 0x02000000 | C_BG; GP0 = XY(0, y); GP0 = XY(FW, FH);
}

static void rect(int x, int y, int w, int h, u32 c)
{
    if (w <= 0 || h <= 0) return;
    gwait(); GP0 = 0x60000000 | c; GP0 = XY(x, y); GP0 = XY(w, h);
}
static void tri(int x0, int y0, int x1, int y1, int x2, int y2, u32 c)
{
    gwait(); GP0 = 0x20000000 | c; GP0 = XY(x0, y0); GP0 = XY(x1, y1); GP0 = XY(x2, y2);
}
static void quad(const int *p, u32 c)   /* p: 4 points, in order around the shape */
{
    gwait(); GP0 = 0x28000000 | c;
    GP0 = XY(p[0], p[1]); GP0 = XY(p[2], p[3]); GP0 = XY(p[6], p[7]); GP0 = XY(p[4], p[5]);
}
static void line(int x0, int y0, int x1, int y1, u32 c)
{
    gwait(); GP0 = 0x40000000 | c; GP0 = XY(x0, y0); GP0 = XY(x1, y1);
}
static void frame(int x, int y, int w, int h, u32 c)
{
    rect(x, y, w, 1, c); rect(x, y + h - 1, w, 1, c); rect(x, y, 1, h, c); rect(x + w - 1, y, 1, h, c);
}

static int isin(int a) { return sin_tab[a & 255]; }
static int icos(int a) { return sin_tab[(a + 64) & 255]; }

static void circle(int cx, int cy, int r, u32 c)
{
    int px = cx + r, py = cy;
    for (int a = 16; a <= 256; a += 16) {
        int x = cx + ((icos(a) * r + 2048) >> 12), y = cy + ((isin(a) * r + 2048) >> 12);
        tri(cx, cy, px, py, x, y, c); px = x; py = y;
    }
}
static void ring(int cx, int cy, int r, int t, u32 c, u32 inner)
{
    circle(cx, cy, r, c); circle(cx, cy, r - t, inner);
}

/* point (x, y) rotated by angle a (256 = full turn) around (cx, cy) */
static void rot(int x, int y, int a, int cx, int cy, int *o)
{
    int c = icos(a), s = isin(a);
    o[0] = cx + ((x * c - y * s + 2048) >> 12);
    o[1] = cy + ((x * s + y * c + 2048) >> 12);
}
static void rrect(int x, int y, int w, int h, int a, int cx, int cy, u32 c)
{
    int p[8];
    rot(x, y, a, cx, cy, p); rot(x + w, y, a, cx, cy, p + 2);
    rot(x + w, y + h, a, cx, cy, p + 4); rot(x, y + h, a, cx, cy, p + 6);
    quad(p, c);
}
static void rcircle(int x, int y, int r, int a, int cx, int cy, u32 c)
{
    int p[2]; rot(x, y, a, cx, cy, p); circle(p[0], p[1], r, c);
}

static u32 lerpc(u32 a, u32 b, int t)   /* t 0..255 */
{
    u32 o = 0;
    for (int s = 0; s < 24; s += 8) {
        int ca = (a >> s) & 255, cb = (b >> s) & 255;
        o |= (u32)(ca + (cb - ca) * t / 255) << s;
    }
    return o;
}

static void text(int x, int y, const char *s, u32 c, int big)
{
    int w = big ? 8 : 6, h = big ? 16 : 9, vb = big ? 96 : 0;
    for (; *s; s++, x += w) {
        int ch = (u8)*s;
        if (ch <= 32 || ch >= 128) continue;
        int i = ch - 32;
        gwait();
        GP0 = 0x64000000 | c; GP0 = XY(x, y);
        GP0 = ((u32)CLUT_ID << 16) | ((u32)(vb + (i >> 4) * 16) << 8) | (u32)((i & 15) * 8);
        GP0 = XY(w, h);
    }
}
static int slen(const char *s) { int n = 0; while (s[n]) n++; return n; }

/* tiny formatting */
static char *put_s(char *o, const char *s) { while (*s) *o++ = *s++; *o = 0; return o; }
static char *put_d(char *o, int v, int sign)
{
    char t[12]; int n = 0; unsigned u;
    if (v < 0) { *o++ = '-'; u = (unsigned)-v; } else { if (sign) *o++ = '+'; u = (unsigned)v; }
    do { t[n++] = (char)('0' + u % 10); u /= 10; } while (u);
    while (n) *o++ = t[--n];
    *o = 0; return o;
}
static char *put_h(char *o, unsigned v)
{
    static const char hx[] = "0123456789ABCDEF";
    *o++ = hx[(v >> 4) & 15]; *o++ = hx[v & 15]; *o = 0; return o;
}

/* --------------------------------------------------------------- pads */
#define PAD_SELECT 0x0100
#define PAD_L3     0x0200
#define PAD_R3     0x0400
#define PAD_START  0x0800
#define PAD_UP     0x1000
#define PAD_RIGHT  0x2000
#define PAD_DOWN   0x4000
#define PAD_LEFT   0x8000
#define PAD_L2     0x0001
#define PAD_R2     0x0002
#define PAD_L1     0x0004
#define PAD_R1     0x0008
#define PAD_TRI    0x0010
#define PAD_CIRCLE 0x0020
#define PAD_X      0x0040
#define PAD_SQUARE 0x0080
#define NEG_THR    0x60

enum { T_NONE, T_PAD, T_MOUSE, T_NEGCON, T_VOLUME, T_JP3 };
static const char *const tname[] = { "", "CONTROLLER", "PS MOUSE", "NEGCON", "NAMCO VOLUME", "JP3 SPINNER" };

typedef struct {
    u8 raw[34];      /* raw[0] = ID, then the report bytes */
    int len;         /* report bytes after the ID */
    int bad;         /* failed reads in a row */
    int type;
    u8 neg, negn, negs, jp3, qprev; s8 qdir;
    u16 btn;         /* active high */
    int dx, dy;      /* mouse: this frame */
    int xacc;        /* mouse X counts / JP3 edges, running total */
    int step;        /* JP3 edges this frame */
    int mvx, mvy;    /* mouse motion dot (smoothed) */
    int peak, peakt;
    int reads, fails;
} Port;
static Port port[2];

static void joy_init(void)
{
    JOY_CTRL = 0x40;            /* reset */
    JOY_BAUD = 0x88;            /* 250 kHz */
    JOY_MODE = 0x0D;            /* 8N1, x1 */
    JOY_CTRL = 0;
}
static int joy_ack(void)
{
    for (int i = 0; i < 2000; i++)
        if (JOY_STAT & 0x200) { JOY_CTRL |= 0x10; I_STAT = ~0x80u; return 1; }
    return 0;
}
static u8 joy_xchg(u8 b)
{
    int t = 4000;
    while (!(JOY_STAT & 1) && --t) ;
    JOY_DATA = b;
    t = 4000;
    while (!(JOY_STAT & 2) && --t) ;
    return JOY_DATA;
}
/* returns number of report bytes after the ID, or -1 */
static int joy_poll(int p, u8 *buf)
{
    int r = -1, n, k;
    u8 id;
    while (JOY_STAT & 2) (void)JOY_DATA;   /* drain */
    JOY_CTRL = 0x1003 | (p << 13);         /* select, TX on, ACK interrupt on */
    delay(120);
    JOY_CTRL |= 0x10;
    I_STAT = ~0x80u;
    joy_xchg(0x01);
    if (!joy_ack()) goto out;
    id = joy_xchg(0x42);
    if (!joy_ack()) goto out;
    if (joy_xchg(0x00) != 0x5A) goto out;
    n = (id & 15) * 2; if (!n) n = 32;
    buf[0] = id;
    for (k = 0; k < n; k++) {
        if (!joy_ack()) break;
        buf[1 + k] = joy_xchg(0x00);
    }
    if (k == n) r = n;
out:
    JOY_CTRL = 0;
    delay(200);
    return r;
}

static void port_reset(Port *p)
{
    p->type = T_NONE; p->len = 0; p->raw[0] = 0;
    p->neg = p->negn = p->negs = p->jp3 = 0; p->qdir = 0;
    p->btn = 0; p->dx = p->dy = p->step = 0;
}

static void port_update(int i)
{
    Port *p = &port[i];
    u8 b[34];
    int n = joy_poll(i, b);
    p->dx = p->dy = p->step = 0;
    p->reads++;
    if (n > 0 && b[0] == 0x23 && (b[4] & b[5] & b[6]) >= 0xF0) n = -1;   /* garbled */
    if (n < 0) {
        p->fails++;
        if (++p->bad >= 30) { p->bad = 30; port_reset(p); }
        return;                         /* otherwise keep showing the last good read */
    }
    p->bad = 0;
    if (b[0] != p->raw[0] || p->type == T_NONE) { port_reset(p); }
    memcpy(p->raw, b, 1 + n); p->len = n;
    u16 w = (u16)~((b[1] << 8) | b[2]);
    p->btn = w;

    if (b[0] == 0x12) {
        p->type = T_MOUSE;
        p->dx = (s8)b[3]; p->dy = (s8)b[4];
        p->xacc += p->dx;
    } else if (b[0] == 0x23) {
        int m = 0;
        if (b[4] > NEG_THR) m |= 1;
        if (b[5] > NEG_THR) m |= 2;
        if (b[6] > NEG_THR) m |= 4;
        if (w & (u16)~(PAD_START | PAD_CIRCLE)) m |= 8;
        if (m) {
            p->negn = (p->negs & m) ? p->negn + 1 : 1;
            p->negs = (u8)m;
            if (p->negn >= 3) p->neg = 1;
        } else { p->negn = 0; p->negs = 0; }
        p->type = p->neg ? T_NEGCON : T_VOLUME;
    } else {
        int a = (w & PAD_LEFT) ? 1 : 0, bb = (w & PAD_RIGHT) ? 1 : 0;
        int pos = a ^ (3 * bb);         /* 00->0 10->1 11->2 01->3 */
        if (!p->jp3 && (w & (PAD_LEFT | PAD_RIGHT)) == (PAD_LEFT | PAD_RIGHT)) {
            p->jp3 = 1; p->qprev = (u8)pos; p->qdir = 0;
        } else if (p->jp3) {
            int d = (pos - p->qprev) & 3;
            p->qprev = (u8)pos;
            if (d == 1) { p->qdir = 1; p->step = 1; }
            else if (d == 3) { p->qdir = -1; p->step = -1; }
            else if (d == 2) p->step = 2 * p->qdir;   /* both phases moved between reads */
            p->xacc += p->step;
        }
        p->type = p->jp3 ? T_JP3 : T_PAD;
    }
}

/* ------------------------------------------------------------ drawing */
static u32 lit(u16 w, u16 m, u32 on) { return (w & m) ? on : C_OFF; }

static void draw_pad(Port *p, int ox, int oy)
{
    u16 w = p->btn;
    int analog = (p->raw[0] >> 4) == 7 || (p->raw[0] >> 4) == 5;
    /* shoulders */
    rect(ox + 20, oy + 22, 32, 6, lit(w, PAD_L2, C_LIT)); rect(ox + 100, oy + 22, 32, 6, lit(w, PAD_R2, C_LIT));
    rect(ox + 20, oy + 30, 32, 6, lit(w, PAD_L1, C_LIT)); rect(ox + 100, oy + 30, 32, 6, lit(w, PAD_R1, C_LIT));
    text(ox + 4, oy + 22, "L2", C_DIM, 0); text(ox + 4, oy + 30, "L1", C_DIM, 0);
    text(ox + 136, oy + 22, "R2", C_DIM, 0); text(ox + 136, oy + 30, "R1", C_DIM, 0);
    /* body */
    circle(ox + 32, oy + 76, 20, C_BODY2); circle(ox + 120, oy + 76, 20, C_BODY2);
    circle(ox + 38, oy + 56, 18, C_BODY); circle(ox + 114, oy + 56, 18, C_BODY);
    rect(ox + 38, oy + 40, 76, 36, C_BODY);
    /* d-pad */
    int cx = ox + 38, cy = oy + 56;
    u32 dl = C_LIT, dr = C_LIT;
    if (p->type == T_JP3) { dl = C_ACC; dr = C_CIR; }
    rect(cx - 4, cy - 13, 9, 9, lit(w, PAD_UP, C_LIT));
    rect(cx - 4, cy + 5, 9, 9, lit(w, PAD_DOWN, C_LIT));
    rect(cx - 13, cy - 4, 9, 9, lit(w, PAD_LEFT, dl));
    rect(cx + 5, cy - 4, 9, 9, lit(w, PAD_RIGHT, dr));
    rect(cx - 4, cy - 4, 9, 9, C_OFF);
    if (p->type == T_JP3) { text(cx - 21, cy - 4, "A", C_TEXT, 0); text(cx + 16, cy - 4, "B", C_TEXT, 0); }
    /* select / start */
    rect(ox + 62, oy + 54, 11, 5, lit(w, PAD_SELECT, C_LIT));
    rect(ox + 80, oy + 54, 11, 5, lit(w, PAD_START, C_LIT));
    /* face buttons */
    cx = ox + 114; cy = oy + 56;
    circle(cx, cy - 10, 6, lit(w, PAD_TRI, C_TRI));
    circle(cx + 10, cy, 6, lit(w, PAD_CIRCLE, C_CIR));
    circle(cx, cy + 10, 6, lit(w, PAD_X, C_CRO));
    circle(cx - 10, cy, 6, lit(w, PAD_SQUARE, C_SQU));
    if (analog && p->len >= 6) {
        int sx[2] = { ox + 58, ox + 94 };
        int vx[2] = { p->raw[5], p->raw[3] }, vy[2] = { p->raw[6], p->raw[4] };
        u16 sm[2] = { PAD_L3, PAD_R3 };
        for (int k = 0; k < 2; k++) {
            ring(sx[k], oy + 82, 12, 2, (w & sm[k]) ? C_LIT : C_LINE, C_OFF);
            circle(sx[k] + (vx[k] - 128) * 8 / 128, oy + 82 + (vy[k] - 128) * 8 / 128, 5, C_FILL);
        }
    }
    if (p->type == T_JP3) {
        int a = p->xacc * 8;   /* 32 edges per turn on screen */
        int wx = ox + 76, wy = oy + 104;
        ring(wx, wy, 15, 3, C_ACC, C_OFF);
        int q[2]; rot(0, -11, a, wx, wy, q);
        line(wx, wy, q[0], q[1], C_LIT);
        circle(q[0], q[1], 3, C_LIT);
    }
}

static void draw_mouse(Port *p, int ox, int oy)
{
    int cx = ox + 48;
    circle(cx, oy + 46, 26, C_BODY); circle(cx, oy + 94, 26, C_BODY);
    rect(cx - 26, oy + 46, 53, 48, C_BODY);
    u32 lb = (p->btn & 0x0008) ? C_LIT : C_OFF, rb = (p->btn & 0x0004) ? C_LIT : C_OFF;
    rect(cx - 20, oy + 28, 19, 30, lb); rect(cx + 2, oy + 28, 19, 30, rb);
    text(cx - 14, oy + 62, "L", C_DIM, 0); text(cx + 8, oy + 62, "R", C_DIM, 0);
    /* motion box */
    int bx = ox + 92, by = oy + 38;
    rect(bx, by, 52, 52, C_OFF); frame(bx, by, 52, 52, C_LINE);
    rect(bx + 25, by + 2, 1, 48, C_LINE); rect(bx + 2, by + 25, 48, 1, C_LINE);
    int dx = p->mvx / 4, dy = p->mvy / 4;
    if (dx > 22) dx = 22; if (dx < -22) dx = -22; if (dy > 22) dy = 22; if (dy < -22) dy = -22;
    circle(bx + 26 + dx, by + 26 + dy, 4, C_FILL);
    text(bx + 2, by + 56, "MOTION", C_DIM, 0);
}

static void draw_negcon(Port *p, int ox, int oy)
{
    u16 w = p->btn;
    int tw = p->raw[3], a = (tw - 128) * 22 / 128;   /* about +-31 degrees */
    int cx = ox + 76, cy = oy + 62;
    /* left half rotates one way, right half the other */
    rrect(-66, -32, 30, 6, a, cx, cy, lerpc(C_OFF, C_LIT, p->raw[6]));     /* L (analog) */
    rrect(36, -32, 30, 6, -a, cx, cy, lit(w, PAD_R1, C_LIT));              /* R */
    rrect(-70, -22, 62, 40, a, cx, cy, C_BODY);
    rcircle(-52, 16, 18, a, cx, cy, C_BODY2);
    rrect(8, -22, 62, 40, -a, cx, cy, C_BODY);
    rcircle(52, 16, 18, -a, cx, cy, C_BODY2);
    circle(cx, cy, 11, C_LINE);
    circle(cx, cy, 5, C_BODY2);
    /* d-pad and START on the left half */
    rrect(-52, -14, 8, 8, a, cx, cy, lit(w, PAD_UP, C_LIT));
    rrect(-52, 2, 8, 8, a, cx, cy, lit(w, PAD_DOWN, C_LIT));
    rrect(-60, -6, 8, 8, a, cx, cy, lit(w, PAD_LEFT, C_LIT));
    rrect(-44, -6, 8, 8, a, cx, cy, lit(w, PAD_RIGHT, C_LIT));
    rrect(-30, 4, 10, 5, a, cx, cy, lit(w, PAD_START, C_LIT));
    /* A, B (digital) and I, II (analog) on the right half */
    rcircle(56, -10, 6, -a, cx, cy, lit(w, PAD_CIRCLE, C_CIR));            /* A */
    rcircle(42, -4, 6, -a, cx, cy, lit(w, PAD_TRI, C_TRI));                /* B */
    rcircle(50, 10, 7, -a, cx, cy, lerpc(C_OFF, C_CRO, p->raw[4]));        /* I */
    rcircle(34, 14, 7, -a, cx, cy, lerpc(C_OFF, C_SQU, p->raw[5]));        /* II */
    char s[40], *o = s;
    o = put_s(o, "I "); o = put_h(o, p->raw[4]); o = put_s(o, "  II "); o = put_h(o, p->raw[5]);
    o = put_s(o, "  L "); put_h(o, p->raw[6]);
    text(ox + 76 - slen(s) * 3, oy + 104, s, C_DIM, 0);
}

static void draw_volume(Port *p, int ox, int oy)
{
    int v = p->raw[3];
    int cx = ox + 56, cy = oy + 66;
    /* scale ticks, 270 degrees */
    for (int k = 0; k <= 8; k++) {
        int a = -96 + k * 24, q0[2], q1[2];
        rot(0, -40, a, cx, cy, q0); rot(0, -34, a, cx, cy, q1);
        line(q0[0], q0[1], q1[0], q1[1], C_DIM);
    }
    circle(cx, cy, 32, C_BODY2);
    circle(cx, cy, 27, C_BODY);
    int a = -96 + v * 192 / 255;
    rrect(-2, -27, 5, 20, a, cx, cy, C_LIT);
    circle(cx, cy, 5, C_BODY2);
    u32 ca = (p->btn & PAD_START) ? C_LIT : C_OFF, cb = (p->btn & PAD_CIRCLE) ? C_LIT : C_OFF;
    circle(ox + 122, oy + 46, 11, ca); circle(ox + 122, oy + 84, 11, cb);
    text(ox + 119, oy + 42, "A", C_TEXT, 0); text(ox + 119, oy + 80, "B", C_TEXT, 0);
    if (p->negn) {   /* NeGcon-only input seen, not yet confirmed */
        char s[24], *o = s; o = put_s(o, "NEGCON? "); put_d(o, p->negn, 0);
        text(ox + 96, oy + 104, s, C_DIM, 0);
    }
}

static void draw_none(int ox, int oy)
{
    rect(ox + 66, oy + 46, 20, 26, C_OFF); rect(ox + 70, oy + 38, 3, 8, C_OFF); rect(ox + 79, oy + 38, 3, 8, C_OFF);
    rect(ox + 74, oy + 72, 4, 24, C_OFF);
    text(ox + 76 - 13 * 3, oy + 104, "NOT CONNECTED", C_DIM, 0);
}

static void draw_panel(int i)
{
    Port *p = &port[i];
    int ox = 4 + i * 158, oy = 24;
    rect(ox, oy, 154, 146, C_PANEL);
    char s[48], *o;
    text(ox + 6, oy + 4, i ? "PLAYER 2" : "PLAYER 1", C_TEXT, 1);
    if (p->type != T_NONE) text(ox + 150 - slen(tname[p->type]) * 6, oy + 8, tname[p->type], RGB(70, 120, 160), 0);
    int dy = oy + 6;
    switch (p->type) {
    case T_NONE: draw_none(ox, dy); break;
    case T_MOUSE: draw_mouse(p, ox, dy); break;
    case T_NEGCON: draw_negcon(p, ox, dy); break;
    case T_VOLUME: draw_volume(p, ox, dy); break;
    default: draw_pad(p, ox, dy); break;
    }
    /* raw report */
    if (p->type != T_NONE) {
        o = s; o = put_s(o, "ID "); o = put_h(o, p->raw[0]); *o++ = ':';
        for (int k = 1; k <= p->len && k <= 8; k++) { *o++ = ' '; o = put_h(o, p->raw[k]); }
        *o = 0;
        text(ox + 4, oy + 134, s, p->bad ? C_CIR : C_DIM, 0);
    }
}

static void draw_bar(int i)
{
    Port *p = &port[i];
    int y = 176 + i * 30, bx = 40, bw = 256, mid = bx + 128;
    char s[64], *o = s;
    text(6, y, i ? "P2 X" : "P1 X", C_TEXT, 0);
    rect(bx - 1, y - 1, bw + 2, 12, C_LINE);
    rect(bx, y, bw, 10, C_OFF);
    int fill = 0, mark = -1, from_left = 0;
    switch (p->type) {
    case T_MOUSE:
        fill = p->dx; mark = (p->xacc + 128) & 255;
        o = put_s(o, "dX "); o = put_d(o, p->dx, 1); o = put_s(o, "  dY "); o = put_d(o, p->dy, 1);
        o = put_s(o, "  TOTAL X "); put_d(o, p->xacc, 0);
        break;
    case T_VOLUME:
        from_left = 1; fill = p->raw[3] + 1;
        o = put_s(o, "KNOB "); o = put_d(o, p->raw[3], 0); o = put_s(o, " (0x"); o = put_h(o, p->raw[3]);
        o = put_s(o, ")  "); o = put_d(o, p->raw[3] * 100 / 255, 0); put_s(o, "%");
        break;
    case T_NEGCON:
        fill = p->raw[3] - 128;
        o = put_s(o, "TWIST "); o = put_d(o, p->raw[3], 0); o = put_s(o, " (0x"); o = put_h(o, p->raw[3]); put_s(o, ")");
        break;
    case T_JP3:
        fill = p->step * 32; mark = (p->xacc * 4 + 128) & 255;
        o = put_s(o, "EDGES "); o = put_d(o, p->step, 1); o = put_s(o, "  TOTAL "); put_d(o, p->xacc, 0);
        break;
    case T_PAD:
        if ((p->raw[0] >> 4) == 7 || (p->raw[0] >> 4) == 5) {
            fill = p->raw[5] - 128;
            o = put_s(o, "LEFT STICK X "); put_d(o, p->raw[5], 0);
        } else {
            if (p->btn & PAD_LEFT) fill = -128;
            if (p->btn & PAD_RIGHT) fill = 127;
            put_s(o, "D-PAD  (L+R TOGETHER = JP3 SPINNER)");
        }
        break;
    default:
        put_s(o, "NOT CONNECTED");
    }
    if (from_left) rect(bx, y, fill > bw ? bw : fill, 10, C_FILL);
    else {
        if (fill > 127) fill = 127; if (fill < -128) fill = -128;
        if (fill > 0) rect(mid, y, fill, 10, C_FILL);
        else if (fill < 0) rect(mid + fill, y, -fill, 10, C_FILL);
        rect(mid, y - 2, 1, 14, C_DIM);
    }
    if (mark >= 0) rect(bx + mark - 1, y - 2, 2, 14, C_MARK);
    text(bx, y + 13, s, C_DIM, 0);
}

static void tick_motion(Port *p)
{
    p->mvx = p->mvx * 3 / 4 + p->dx * 4;
    p->mvy = p->mvy * 3 / 4 + p->dy * 4;
}

/* exported for the test harness */
volatile u32 frame_count;
Port *volatile port_ptr;

int main(void)
{
    I_MASK = 0;                 /* no interrupts: everything is polled */
    I_STAT = 0;
    gpu_init();
    joy_init();
    port_reset(&port[0]); port_reset(&port[1]);
    port_ptr = port;
    db = 1;
    for (;;) {
        port_update(0); port_update(1);
        tick_motion(&port[0]); tick_motion(&port[1]);
        begin_frame();
        text(8, 5, "CONTROLLER TEST", C_TEXT, 1);
        text(280, 9, "v1.0", RGB(60, 70, 100), 0);
        draw_panel(0); draw_panel(1);
        draw_bar(0); draw_bar(1);
        gwait();
        /* vblank: show what was just drawn */
        I_STAT = ~1u;
        while (!(I_STAT & 1)) ;
        GP1 = 0x05000000 | ((u32)(db ? 256 : 0) << 10);
        if (frame_count == 0) GP1 = 0x03000000;   /* display on after the first frame */
        db ^= 1;
        frame_count++;
    }
}
