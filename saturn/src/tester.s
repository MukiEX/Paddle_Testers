! Sega Saturn controller tester - loaded by the BIOS as 1st read file at 0x06004000.
! Top half: two pad diagrams (VDP2 NBG0 8bpp bitmap; every button has its own
! palette index, so lighting a button is a colour RAM write).
! Bottom half: oscilloscope sweep of LEFT / RIGHT / Y / Z for both ports,
! one pixel column per frame, red where both of a pair are held at once.
        .include "build/consts.inc"
        .equ BASE,   0x06004000
        .equ VRAM,   0x25E00000
        .equ CRAM,   0x25F00000
        .equ VDP2,   0x25F80000
        .macro ABS sym
        .long (\sym - _start) + BASE
        .endm

        .text
        .global _start
_start:
        mov.l   L_srmask, r0
        ldc     r0, sr
        mov.l   L_stack, r15
        bsr     init
        nop
mainloop:
        bsr     wait_vblank
        nop
        bsr     read_pads               ! result of last frame's INTBACK (ready at ~line 207)
        nop
        bsr     apply_palette
        nop
        bsr     issue_intback           ! completes just before the next vblank (OPE)
        nop
        bsr     draw_trace
        nop
        bsr     draw_text
        nop
        bra     mainloop
        nop
        .align 2
L_srmask: .long 0x000000F0
L_stack:  .long 0x060FFF00

! ------------------------------------------------------------------ init
init:
        sts.l   pr, @-r15
        ! VDP2 registers
        mov.l   I_regs, r1
        mov.l   I_vdp2, r2
1:      mov.w   @r1+, r0
        cmp/eq  #-1, r0
        bt      2f
        mov.w   @r1+, r3
        bra     1b
        mov.w   r3, @(r0, r2)
2:      ! palette 256 words
        mov.l   I_pal, r1
        mov.l   I_cram, r2
        mov.w   I_256, r3
3:      mov.w   @r1+, r0
        mov.w   r0, @r2
        dt      r3
        bf/s    3b
        add     #2, r2
        ! bitmap: 512*224 bytes = 28672 longs
        mov.l   I_bg, r1
        mov.l   I_vram, r2
        mov.l   I_nlong, r3
4:      mov.l   @r1+, r0
        mov.l   r0, @r2
        dt      r3
        bf/s    4b
        add     #4, r2
        ! back screen colour word (VRAM 0x3FFFE) = black
        mov.l   I_back, r2
        mov     #0, r0
        mov.w   r0, @r2
        ! VDP1: END command at top of command table so it draws nothing
        mov.l   I_vdp1, r2
        mov.w   I_8000, r0
        mov.w   r0, @r2
        ! clear state block
        mov.l   I_state, r1
        mov     #64, r3
        mov     #0, r0
5:      mov.l   r0, @r1
        dt      r3
        bf/s    5b
        add     #4, r1
        mov.l   I_ports, r1
        mov     #-1, r0
        mov.b   r0, @r1
        add     #16, r1
        mov.b   r0, @r1
        ! display on: 320x224, non-interlaced
        mov.l   I_vdp2, r2
        mov.w   I_8000, r0
        mov.w   r0, @r2
        lds.l   @r15+, pr
        rts
        nop
        .align 2
I_256:   .word 256
I_8000:  .word 0x8000
I_regs:  ABS vdp2_regs
I_vdp2:  .long VDP2
I_pal:   ABS pal
I_cram:  .long CRAM
I_bg:    ABS bg
I_vram:  .long VRAM
I_nlong: .long 512*224/4
I_back:  .long VRAM + 0x3FFFE
I_vdp1:  .long 0x25C00000
I_state: ABS state
I_ports: ABS ports

! ------------------------------------------------------------------ vblank
wait_vblank:
        mov.l   W_tvstat, r1
1:      mov.w   @r1, r0
        tst     #8, r0
        bf      1b
2:      mov.w   @r1, r0
        tst     #8, r0
        bt      2b
        rts
        nop
        .align 2
W_tvstat: .long VDP2 + 4

! ------------------------------------------------------------------ pads
! SMPC INTBACK, peripheral data only, 15-byte mode both ports.
! ports[p] (16 bytes): +0 id (0xFF none) +1 len +2..+9 data +10 status
!                      +12 word: buttons, active high (0 if not a pad-type device)
issue_intback:
        mov.l   R_sf, r1
1:      mov.b   @r1, r0
        tst     #1, r0
        bf      1b
        mov.l   R_ireg, r2
        mov     #0, r0
        mov.b   r0, @r2                 ! IREG0: no status
        mov     #0x0A, r0
        mov.b   r0, @(2, r2)            ! IREG1: peripheral data, 15-byte mode, OPE
        mov     #-16, r0
        mov.b   r0, @(4, r2)            ! IREG2: 0xF0
        mov     #1, r0
        mov.b   r0, @r1                 ! SF = 1
        mov.l   R_com, r3
        mov     #0x10, r0
        mov.b   r0, @r3                 ! COMREG: INTBACK
        rts
        nop

read_pads:
        mov.l   R_sf, r1
        mov.l   R_ireg, r2
        mov.l   R_timeout, r7
2:      mov.b   @r1, r0
        tst     #1, r0
        bt      3f
        dt      r7
        bf      2b
3:      mov.l   R_oreg, r4
        mov.l   R_buf, r5
        mov     #32, r6
4:      mov.b   @r4, r0
        add     #2, r4
        mov.b   r0, @r5
        dt      r6
        bf/s    4b
        add     #1, r5
        mov.l   R_sr, r3
        mov.b   @r3, r0
        tst     #0x20, r0
        bt      31f
        mov     #0x40, r0
        mov.b   r0, @r2                 ! IREG0: break (more data pending, e.g. multitap)
31:
        ! ---- parse
        mov.l   R_buf, r4
        mov     r4, r9
        add     #32, r9                 ! end of buffer
        mov.l   R_ports, r5
        mov     #2, r6
pport:
        mov     #-1, r0
        mov.b   r0, @r5
        mov     #0, r0
        mov.b   r0, @(1, r5)
        mov.w   r0, @(12, r5)
        cmp/hs  r9, r4
        bt      pnext
        mov.b   @r4+, r0
        extu.b  r0, r7                  ! port status
        mov     r7, r0
        mov.b   r0, @(10, r5)
        and     #15, r0
        mov     r0, r8                  ! connectors
        tst     r8, r8
        bt      pnext
        mov     #0, r10                 ! k
pperi:
        cmp/hs  r9, r4
        bt      pnext
        mov.b   @r4+, r0
        extu.b  r0, r11                 ! id
        mov     #0, r12                 ! len
        mov     r11, r0
        mov.w   R_ff, r3
        cmp/eq  r3, r11
        bt      5f
        and     #15, r0
        mov     r0, r12
        cmp/eq  #15, r0
        bf      5f
        mov.b   @r4+, r0
        extu.b  r0, r12
5:      tst     r10, r10
        bf      7f
        ! first peripheral on this port: record it
        mov     r11, r0
        mov.b   r0, @r5
        mov     r12, r0
        mov.b   r0, @(1, r5)
        mov     r12, r3
        mov     #8, r0
        cmp/gt  r0, r3
        bf      55f
        mov     #8, r3
55:     mov     r4, r13
        mov     r5, r14
        add     #2, r14
        tst     r3, r3
        bt      7f
6:      mov.b   @r13+, r0
        mov.b   r0, @r14
        dt      r3
        bf/s    6b
        add     #1, r14
7:      add     r12, r4
        add     #1, r10
        cmp/hs  r8, r10
        bf      pperi
pnext:
        ! buttons word for pad-type devices (id type nibble 0 = digital, 1 = analog)
        mov.b   @r5, r0
        extu.b  r0, r0
        shlr2   r0
        shlr2   r0
        cmp/eq  #15, r0                 ! 0xFF none
        bt      8f
        mov     #1, r3
        cmp/hi  r3, r0
        bt      8f
        mov.b   @(1, r5), r0
        cmp/hi  r3, r0                  ! need len >= 2
        bf      8f
        mov.b   @(2, r5), r0
        extu.b  r0, r3
        shll8   r3
        mov.b   @(3, r5), r0
        extu.b  r0, r0
        or      r0, r3
        not     r3, r3
        mov.w   R_mask, r0
        and     r0, r3
        mov     r3, r0
        mov.w   r0, @(12, r5)
8:      add     #16, r5
        dt      r6
        bf      pport
        rts
        nop
        .align 2
R_ff:    .word 0xFF
R_mask:  .word 0xFFF8
R_sf:    .long 0x20100063
R_ireg:  .long 0x20100001
R_com:   .long 0x2010001F
R_oreg:  .long 0x20100021
R_sr:    .long 0x20100061
R_timeout: .long 400000
R_buf:   ABS oreg_buf
R_ports: ABS ports

! ------------------------------------------------------------------ palette
! For each port and each of the 13 buttons write fill + label colours.
apply_palette:
        mov.l   P_ports, r8
        mov.l   P_fill, r2              ! CRAM + 32*2
        mov.l   P_lab, r3               ! CRAM + 64*2
        mov     #2, r9
1:      mov.w   @(12, r8), r0
        mov     r0, r4
        shll16  r4
        mov.l   P_cols, r1
        mov     #13, r5
2:      shll    r4
        movt    r0
        add     r0, r0
        add     r1, r0
        mov     r0, r6
        mov.w   @r6, r7
        mov.w   @(4, r6), r0
        mov.w   r7, @r2
        mov.w   r0, @r3
        add     #2, r2
        add     #2, r3
        dt      r5
        bf/s    2b
        add     #8, r1
        add     #6, r2                  ! skip to next 16-entry block
        add     #6, r3
        add     #16, r8
        dt      r9
        bf      1b
        rts
        nop
        .align 2
P_ports: ABS ports
P_fill:  .long CRAM + 32*2
P_lab:   .long CRAM + 64*2
P_cols:  ABS btncol

! ------------------------------------------------------------------ traces
draw_trace:
        sts.l   pr, @-r15
        mov.l   T_state, r12
        mov.w   @r12, r0                ! sweep position
        mov     r0, r10
        mov.w   T_tw, r1
        add     #1, r0
        cmp/hs  r1, r0
        bf      1f
        mov     #0, r0
1:      mov.w   r0, @r12
        mov     r0, r11                 ! next position (cursor)
        ! column address
        mov.l   T_col0, r13
        add     r10, r13
        mov.l   T_ports, r8
        mov.l   T_pats, r9
        mov     #2, r14                 ! ports
tport:
        mov.w   @(12, r8), r0
        extu.w  r0, r4
        ! pair masks
        mov     r4, r0
        mov.w   T_lr, r1
        extu.w  r1, r1
        and     r1, r0
        cmp/eq  r1, r0
        movt    r6                      ! r6 = both LEFT+RIGHT
        mov     r4, r0
        mov     #0x30, r1
        and     r1, r0
        cmp/eq  r1, r0
        movt    r7                      ! r7 = both Y+Z
        ! counters: state +4 (p0 lr) +6 (p0 yz) +8 (p1 lr) +10 (p1 yz)
        mov     #2, r0
        sub     r14, r0                 ! port index 0/1
        shll2   r0
        add     r12, r0
        mov     r0, r5                  ! &counter pair - 4
        ! A+B+C+START clears this port's counters
        mov.w   T_rst, r1
        mov     r4, r0
        and     r1, r0
        cmp/eq  r1, r0
        bf      3f
        mov     #0, r0
        mov.w   r0, @(4, r5)
        mov.w   r0, @(6, r5)
3:      tst     r6, r6
        bt      4f
        mov.w   @(4, r5), r0
        add     #1, r0
        mov.w   r0, @(4, r5)
4:      tst     r7, r7
        bt      5f
        mov.w   @(6, r5), r0
        add     #1, r0
        mov.w   r0, @(6, r5)
5:      ! four traces: LEFT bit14 RIGHT bit15 Y bit5 Z bit4
        mov.w   T_left, r1
        bsr     trace_one
        mov     r6, r3
        mov.w   T_right, r1
        bsr     trace_one
        mov     r6, r3
        mov     #0x20, r1
        bsr     trace_one
        mov     r7, r3
        mov     #0x10, r1
        bsr     trace_one
        mov     r7, r3
        add     #16, r8
        dt      r14
        bf      tport
        ! cursor column at next position
        mov.l   T_col0, r13
        add     r11, r13
        mov     #96, r3
        mov     #CURSOR, r0
        mov.w   T_512, r1
6:      mov.b   r0, @r13
        dt      r3
        bf/s    6b
        add     r1, r13
        lds.l   @r15+, pr
        rts
        nop
! r4 buttons, r1 bit mask, r3 pair-both flag, r9 pattern ptr (advanced 36), r13 column (advanced 12 rows)
trace_one:
        mov     #0, r2
        tst     r1, r4
        bt      1f
        mov     #12, r2
        tst     r3, r3
        bt      1f
        mov     #24, r2
1:      add     r9, r2
        mov     #12, r3
        mov.w   T_512, r1
2:      mov.b   @r2+, r0
        mov.b   r0, @r13
        dt      r3
        bf/s    2b
        add     r1, r13
        rts
        add     #36, r9
        .align 2
T_tw:    .word TW
T_512:   .word 512
T_rst:   .word 0x0F00
T_lr:    .word 0xC000
T_left:  .word 0x4000
T_right: .word 0x8000
T_state: ABS state
T_col0:  .long VRAM + TY0*512 + TX0
T_ports: ABS ports
T_pats:  ABS pats

! ------------------------------------------------------------------ text
! draw_str: r4 = string, r5 = x, r6 = y. 6x13 glyphs, fg TEXT on bg BG.
draw_str:
        mov     r6, r0
        shll8   r0
        shll    r0
        add     r5, r0
        mov.l   S_vram, r7
        add     r0, r7                  ! r7 = top-left of next char
1:      mov.b   @r4+, r0
        extu.b  r0, r0
        tst     r0, r0
        bt      9f
        add     #-32, r0
        shll2   r0
        shll2   r0
        mov.l   S_font, r1
        add     r0, r1                  ! glyph
        mov     r7, r2
        mov     #13, r3
2:      mov.b   @r1+, r0
        extu.b  r0, r5
        shll16  r5
        shll8   r5
        mov     #6, r6
3:      shll    r5
        bt/s    4f
        mov     #TEXT, r0
        mov     #BG, r0
4:      mov.b   r0, @r2
        dt      r6
        bf/s    3b
        add     #1, r2
        mov.w   S_506, r0
        dt      r3
        bf/s    2b
        add     r0, r2
        bra     1b
        add     #6, r7
9:      rts
        nop
        .align 2
S_506:   .word 506
         .word 0
S_vram:  .long VRAM
S_font:  ABS font

! hex byte r0 -> 2 chars at @r1+ (uses r2, r3)
put_hex:
        mov.l   H_digits, r2
        mov     r0, r3
        shlr2   r0
        shlr2   r0
        and     #15, r0
        mov.b   @(r0, r2), r0
        mov.b   r0, @r1
        add     #1, r1
        mov     r3, r0
        and     #15, r0
        mov.b   @(r0, r2), r0
        mov.b   r0, @r1
        rts
        add     #1, r1
! decimal (0..65535) r0 -> 5 chars at @r1+ (uses r2, r3, r5)
put_dec:
        mov.l   H_pow, r2
        mov     #5, r5
1:      mov.l   @r2+, r3
        mov     #48, r6
2:      cmp/hs  r3, r0
        bf      3f
        sub     r3, r0
        bra     2b
        add     #1, r6
3:      mov.b   r6, @r1
        dt      r5
        bf/s    1b
        add     #1, r1
        rts
        nop
        .align 2
H_digits: ABS hexdigits
H_pow:    ABS pow10

draw_text:
        sts.l   pr, @-r15
        mov.l   D_ports, r8
        mov     #0, r9                  ! port index
        mov.l   D_state, r12
tloop:
        ! ---------- header: "ID xx NAME"
        mov.l   D_buf, r1
        mov.b   @r8, r0
        extu.b  r0, r10
        mov     r10, r0
        bsr     put_hex
        nop
        mov     #32, r0
        mov.b   r0, @r1
        add     #1, r1
        ! name lookup
        mov.l   D_names, r2
1:      mov.b   @r2, r0
        extu.b  r0, r0
        cmp/eq  r0, r10
        bt      2f
        tst     r0, r0                  ! 0 terminates table (UNKNOWN entry)
        bt      2f
        bra     1b
        add     #20, r2
2:      add     #1, r2
        mov     #18, r3
3:      mov.b   @r2+, r0
        mov.b   r0, @r1
        dt      r3
        bf/s    3b
        add     #1, r1
        mov     #0, r0
        mov.b   r0, @r1
        mov.l   D_buf, r4
        mov     r9, r5
        mov.w   D_160, r0
        mulu.w  r0, r5
        sts     macl, r5
        add     #22, r5
        mov     #2, r6
        bsr     draw_str
        mov     r5, r13                 ! keep x0+22
        ! ---------- raw bytes
        mov.l   D_buf, r1
        mov.b   @(1, r8), r0
        extu.b  r0, r10                 ! len
        mov     r8, r11
        add     #2, r11
        mov     #0, r14
4:      cmp/hs  r10, r14
        bt      5f
        mov.b   @r11, r0
        bsr     put_hex
        nop
        bra     6f
        nop
5:      mov     #32, r0
        mov.b   r0, @r1
        add     #1, r1
        mov.b   r0, @r1
        add     #1, r1
6:      mov     #32, r0
        mov.b   r0, @r1
        add     #1, r1
        add     #1, r11
        add     #1, r14
        mov     #6, r0
        cmp/hs  r0, r14
        bf      4b
        mov     #0, r0
        mov.b   r0, @r1
        mov.l   D_buf, r4
        mov     r13, r5
        add     #12, r5                 ! x0+34
        mov     #89, r6
        bsr     draw_str
        nop
        ! ---------- both-held counters "LR 00000  YZ 00000"
        mov.l   D_buf, r1
        mov     #76, r0
        mov.b   r0, @r1
        mov     #82, r0
        mov.b   r0, @(1, r1)
        mov     #32, r0
        mov.b   r0, @(2, r1)
        add     #3, r1
        mov     r9, r0
        shll2   r0
        add     r12, r0
        mov     r0, r11
        mov.w   @(4, r11), r0
        bsr     put_dec
        extu.w  r0, r0
        mov     #32, r0
        mov.b   r0, @r1
        mov.b   r0, @(1, r1)
        mov     #89, r0
        mov.b   r0, @(2, r1)
        mov     #90, r0
        mov.b   r0, @(3, r1)
        mov     #32, r0
        mov.b   r0, @(4, r1)
        add     #5, r1
        mov.w   @(6, r11), r0
        bsr     put_dec
        extu.w  r0, r0
        mov     #0, r0
        mov.b   r0, @r1
        mov.l   D_buf, r4
        mov     r13, r5
        add     #12, r5
        mov     #101, r6
        bsr     draw_str
        nop
        add     #16, r8
        add     #1, r9
        mov     r9, r0
        cmp/eq  #2, r0
        bf      tloop
        lds.l   @r15+, pr
        rts
        nop
        .align 2
D_160:   .word 160
         .word 0
D_ports: ABS ports
D_state: ABS state
D_buf:   ABS strbuf
D_names: ABS names

! ------------------------------------------------------------------ data
        .align 2
vdp2_regs:
        .word 0x00, 0x0000      ! TVMD: display off during setup
        .word 0x02, 0x0000      ! EXTEN
        .word 0x06, 0x0000      ! VRSIZE
        .word 0x0E, 0x0000      ! RAMCTL: colour RAM mode 0 (RGB555 x1024), no partition
        .word 0x10, 0x44FF      ! CYCA0L: NBG0 character/bitmap reads T0,T1
        .word 0x12, 0xFFFF
        .word 0x14, 0xFFFF
        .word 0x16, 0xFFFF
        .word 0x18, 0xFFFF
        .word 0x1A, 0xFFFF
        .word 0x1C, 0xFFFF
        .word 0x1E, 0xFFFF
        .word 0x20, 0x0101      ! BGON: NBG0 on, transparency off (index 0 drawn)
        .word 0x22, 0x0000      ! MZCTL
        .word 0x24, 0x0000      ! SFSEL
        .word 0x26, 0x0000      ! SFCODE
        .word 0x28, 0x0012      ! CHCTLA: NBG0 bitmap 512x256, 256 colours
        .word 0x2A, 0x0000      ! CHCTLB
        .word 0x2C, 0x0000      ! BMPNA
        .word 0x2E, 0x0000      ! BMPNB
        .word 0x3A, 0x0000      ! PLSZ
        .word 0x3C, 0x0000      ! MPOFN: bitmap at VRAM 0
        .word 0x70, 0x0000      ! SCXIN0
        .word 0x72, 0x0000
        .word 0x74, 0x0000      ! SCYIN0
        .word 0x76, 0x0000
        .word 0x78, 0x0001      ! ZMXIN0 = 1.0
        .word 0x7A, 0x0000
        .word 0x7C, 0x0001      ! ZMYIN0 = 1.0
        .word 0x7E, 0x0000
        .word 0x98, 0x0000      ! ZMCTL
        .word 0x9A, 0x0000      ! SCRCTL
        .word 0xAC, 0x0001      ! BKTAU: back screen colour at VRAM 0x3FFFE
        .word 0xAE, 0xFFFF      ! BKTAL
        .word 0xC0, 0x0000      ! WCTLA..D: windows off
        .word 0xC2, 0x0000
        .word 0xC4, 0x0000
        .word 0xC6, 0x0000
        .word 0xE0, 0x0000      ! SPCTL
        .word 0xE2, 0x0000      ! SDCTL
        .word 0xE4, 0x0000      ! CRAOFA
        .word 0xE6, 0x0000      ! CRAOFB
        .word 0xE8, 0x0000      ! LNCLEN
        .word 0xEA, 0x0000      ! SFPRMD
        .word 0xEC, 0x0000      ! CCCTL
        .word 0xEE, 0x0000      ! SFCCMD
        .word 0xF0, 0x0000      ! PRISA..PRISD: sprites hidden
        .word 0xF2, 0x0000
        .word 0xF4, 0x0000
        .word 0xF6, 0x0000
        .word 0xF8, 0x0007      ! PRINA: NBG0 priority 7, NBG1 0
        .word 0xFA, 0x0000      ! PRINB
        .word 0xFC, 0x0000      ! PRIR
        .word 0x110, 0x0000     ! CLOFEN
        .word 0x112, 0x0000     ! CLOFSL
        .word 0xFFFF
hexdigits: .ascii "0123456789ABCDEF"
        .align 2
pow10:  .long 10000, 1000, 100, 10, 1
! names: 20-byte records: id, 18 chars, pad. id 0 record = fallback.
names:
        .byte 0x02
        .ascii "DIGITAL PAD       "
        .byte 0
        .byte 0x16
        .ascii "3D PAD (ANALOG)   "
        .byte 0
        .byte 0x13
        .ascii "RACING WHEEL      "
        .byte 0
        .byte 0x15
        .ascii "MISSION STICK     "
        .byte 0
        .byte 0x19
        .ascii "DUAL MISSION STICK"
        .byte 0
        .byte 0xE3
        .ascii "SHUTTLE MOUSE     "
        .byte 0
        .byte 0x34
        .ascii "KEYBOARD          "
        .byte 0
        .byte 0xFF
        .ascii "NOT CONNECTED     "
        .byte 0
        .byte 0x00
        .ascii "OTHER DEVICE      "
        .byte 0
        .align 2
btncol: .incbin "build/btncol.bin"
pats:   .incbin "build/pats.bin"
        .align 4
font:   .incbin "build/font.bin"
pal:    .incbin "build/pal.bin"
        .align 4
state:  .space 256              ! +0 sweep pos, +4.. counters
ports:  .space 32
oreg_buf: .space 32
strbuf: .space 64
        .align 4
bg:     .incbin "build/bg.bin"
