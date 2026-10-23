; =====================================================================
;  Neo Geo pad + spinner tester
;
;  Top:    both players' pads (Neo Geo CD style), lit as you press them,
;          plus START / SELECT / COIN.
;  Bottom: a spinner detector per port that recognises
;           - a Taito F3 / JP3-style encoder: quadrature on LEFT (A) and
;             RIGHT (B), A leading B = clockwise = +1
;           - a Pop 'n Bounce-style 7-bit dial: the position in bits 0-6
;  Both ports are sampled about 3,900 times a second from the LSPC
;  raster timer (IRQ2), so fast spins are counted exactly.
; =====================================================================

REG_P1CNT       equ $300000
REG_DIPSW       equ $300001         ; write = kick watchdog
REG_STATUS_A    equ $320001         ; bit0 COIN1, bit1 COIN2 (active low)
REG_P2CNT       equ $340000
REG_STATUS_B    equ $380000         ; bit0 P1 START, 1 P1 SELECT, 2 P2 START, 3 P2 SELECT
REG_SWPROM      equ $3a0013
REG_CRTFIX      equ $3a001b
REG_VRAMADDR    equ $3c0000
REG_VRAMRW      equ $3c0002
REG_VRAMMOD     equ $3c0004
REG_LSPCMODE    equ $3c0006
REG_TIMERHIGH   equ $3c0008
REG_TIMERLOW    equ $3c000a
REG_IRQACK      equ $3c000c
PALETTES        equ $400000
BACKDROP        equ $401ffe
BIOS_SYSTEM_MODE equ $10fd80

FIX             equ $7000           ; fix map: FIX + x*32 + y
LSPC_BITS       equ $00d8           ; no auto-anim | timer IRQ | reload at vblank | repeat
TIMER_RELOAD    equ 4*384-1         ; every 4 lines

; text palettes
P_TEXT          equ 3<<12
P_GOOD          equ 4<<12
P_DIM           equ 5<<12
P_HEAD          equ 6<<12
P_BAD           equ 7<<12

; ---- RAM ----
RAM             equ $100000
VBL             equ RAM+$00         ; .w VBlank counter
SPD_T           equ RAM+$02         ; .w frames since the speed sample
PL1             equ RAM+$40
PL2             equ RAM+$80
PL_SIZE         equ $40
; per player
Q_PH            equ 0               ; .b last L/R phase (bit0 L, bit1 R)
RAWA            equ 1               ; .b last port byte, active high
Q_CNT           equ 2               ; .w encoder count
Q_ERR           equ 4               ; .w skipped samples (both phases changed)
Q_GOOD          equ 6               ; .w clean steps (only L/R changed)
Q_BAD           equ 8               ; .w L/R changes that came with other bits
Q_DET           equ 10              ; .b encoder recognised
D_DET           equ 11              ; .b dial recognised
D_POS           equ 12              ; .b last 7-bit value
D_RUN           equ 13              ; .b consecutive small steps the same way
D_SIGN          equ 14              ; .b sign of that run (0 = +, $FF = -)
D_LAST          equ 15              ; .b last delta
D_CNT           equ 16              ; .w dial count (sum of deltas)
Q_ACT           equ 18              ; .w VBL of the last encoder step
D_ACT           equ 20              ; .w VBL of the last dial step
Q_SPD0          equ 22              ; .w count at the last speed sample
Q_SPD           equ 24              ; .w counts per second
D_SPD0          equ 26
D_SPD           equ 28
; the same encoder fields for the d-pad pairs wiring sit PAIRS bytes higher
PAIRS           equ 32
P_PH            equ 38              ; .b last pairs phase (bit0 LEFT|RIGHT, bit1 UP|DOWN)
P_DET           equ 39              ; .b pairs wiring recognised
P_RUN           equ 40              ; .b signed run of same-way pairs steps
P_IDLE          equ 42              ; .w samples since the last pairs step
PAIR_RUN        equ 12              ; steps the same way, each within
PAIR_IDLE       equ 120             ; this many samples (~30 ms): a quick spin

; =====================================================================
        org     $000000
        dc.l    $0010f300, $00c00402, $00c00408, $00c0040e
        dc.l    $00c00414, ex_rte, ex_rte, ex_rte
        dc.l    $00c0041a, $00c00420, ex_rte, ex_rte
        dc.l    $00c00426, $00c00426, $00c00426, $00c0042c
        dcb.l   8,$00c00426
        dc.l    $00c00432, vbl_handler, irq2_handler, ex_rte
        dcb.l   4,ex_rte
        dcb.l   16,ex_rte
        dcb.l   16,$ffffffff

; ---- cartridge header ----
        org     $000100
        dc.b    "NEO-GEO",0
        dc.w    $0420               ; NGH (homebrew; avoids every special-cased number)
        dc.l    $00100000           ; P ROM size
        dc.l    $0010f000           ; backup RAM (unused)
        dc.w    $0000
        dc.b    1                   ; eye catcher: done by the game (we skip it)
        dc.b    0
        dc.l    dips_jp, dips_us, dips_eu
        jmp     user                ; $122 USER
        jmp     player_start        ; $128
        jmp     demo_end            ; $12e
        jmp     coin_sound          ; $134

        org     $000182
        dc.l    security_code
        include "security.inc"

dips_jp:
dips_us:
dips_eu:
        dc.b    "PAD TEST        "
        dc.b    $ff,$ff,$ff,$ff,$ff,$ff
        dcb.b   10,0
        even

ex_rte:
        rte
player_start:
demo_end:
coin_sound:
        rts

; =====================================================================
;  Interrupts
; =====================================================================
vbl_handler:
        btst    #7,BIOS_SYSTEM_MODE
        bne.s   .ours
        jmp     $c00438             ; BIOS still in charge
.ours:  move.w  #4,REG_IRQACK
        move.b  d0,REG_DIPSW        ; watchdog
        addq.w  #1,VBL
        rte

; quadrature step for prev<<2 | cur, phase = R<<1 | L
; forward {A,B}: 00 -> 10 -> 11 -> 01 == phase 0 -> 1 -> 3 -> 2 -> 0
qtab:
        dc.b     0, 1,-1, 0
        dc.b    -1, 0, 0, 1
        dc.b     1, 0, 0,-1
        dc.b     0,-1, 1, 0

irq2_handler:
        move.w  #2,REG_IRQACK
        movem.l d0-d3/a0-a1,-(sp)
        lea     PL1,a0
        move.b  REG_P1CNT,d0
        bsr.s   sample
        lea     PL2,a0
        move.b  REG_P2CNT,d0
        bsr.s   sample
        movem.l (sp)+,d0-d3/a0-a1
        rte

; d0.b = port (active low), a0 = player
sample:
        not.b   d0                  ; active high
        move.b  RAWA(a0),d3         ; previous byte
        move.b  d0,RAWA(a0)
        ; --- encoder on LEFT (A) / RIGHT (B) ---
        moveq   #0,d1
        move.b  d0,d1
        lsr.b   #2,d1
        andi.w  #3,d1               ; phase
        moveq   #0,d2
        move.b  Q_PH(a0),d2
        cmp.b   d1,d2
        beq.s   .dial
        move.b  d1,Q_PH(a0)
        add.b   d2,d2
        add.b   d2,d2
        or.b    d1,d2
        move.b  qtab(pc,d2.w),d2
        bne.s   .step
        addq.w  #1,Q_ERR(a0)        ; both lines changed: direction unknown
        bra.s   .dial
.step:  ext.w   d2
        add.w   d2,Q_CNT(a0)
        move.w  VBL,Q_ACT(a0)
        move.b  d0,d2               ; did anything besides L/R change?
        eor.b   d3,d2
        andi.b  #$f3,d2
        bne.s   .bad
        addq.w  #1,Q_GOOD(a0)
        cmpi.w  #12,Q_GOOD(a0)      ; clean steps, and few others: an encoder
        bcs.s   .dial
        move.w  Q_BAD(a0),d2
        add.w   Q_ERR(a0),d2
        lsl.w   #2,d2
        cmp.w   Q_GOOD(a0),d2
        bcc.s   .dial
        st      Q_DET(a0)
        bra.s   .dial
.bad:   addq.w  #1,Q_BAD(a0)
        ; --- 7-bit dial in bits 0-6 ---
        ; --- encoder across the d-pad pairs: A = LEFT|RIGHT, B = UP|DOWN
        ; (an encoder wired inside a real pad). Latches on PAIR_RUN quick
        ; steps the same way, like the Paddle Edition patches.
.dial:  move.b  d0,d2
        andi.b  #$0c,d2
        sne     d2
        andi.b  #1,d2
        move.b  d0,d1
        andi.b  #$03,d1
        sne     d1
        andi.b  #2,d1
        or.b    d2,d1
        andi.w  #3,d1               ; pairs phase
        moveq   #0,d2
        move.b  P_PH(a0),d2
        cmp.b   d1,d2
        bne.s   .pchg
        addq.w  #1,P_IDLE(a0)
        cmpi.w  #PAIR_IDLE,P_IDLE(a0)
        bcs.s   .dial7
        move.w  #PAIR_IDLE,P_IDLE(a0)
        clr.b   P_RUN(a0)
        bra.s   .dial7
.pchg:  move.b  d1,P_PH(a0)
        clr.w   P_IDLE(a0)
        add.b   d2,d2
        add.b   d2,d2
        or.b    d1,d2
        lea     qtab(pc),a1
        move.b  (a1,d2.w),d2
        bne.s   .pstep
        addq.w  #1,PAIRS+Q_ERR(a0)  ; both lines changed
        clr.b   P_RUN(a0)
        bra.s   .dial7
.pstep: ext.w   d2
        add.w   d2,PAIRS+Q_CNT(a0)
        move.w  VBL,PAIRS+Q_ACT(a0)
        tst.b   P_DET(a0)
        bne.s   .dial7
        move.b  P_RUN(a0),d1
        eor.b   d2,d1
        bmi.s   .pnew               ; turned the other way
        add.b   d2,P_RUN(a0)
        move.b  P_RUN(a0),d1
        bpl.s   .pabs
        neg.b   d1
.pabs:  cmpi.b  #PAIR_RUN,d1
        bcs.s   .dial7
        st      P_DET(a0)
        bra.s   .dial7
.pnew:  move.b  d2,P_RUN(a0)
        ; --- 7-bit dial in bits 0-6 ---
.dial7: move.b  d0,d1
        andi.b  #$7f,d1
        move.b  D_POS(a0),d2
        cmp.b   d1,d2
        beq.s   .done
        move.b  d1,D_POS(a0)
        sub.b   d2,d1               ; delta, as a 7-bit signed number
        add.b   d1,d1
        asr.b   #1,d1
        move.b  d1,d2
        bpl.s   .abs
        neg.b   d2
.abs:   cmpi.b  #3,d2               ; a dial moves a step or three at a time
        bhi.s   .jump
        move.b  d1,D_LAST(a0)
        ext.w   d1
        add.w   d1,D_CNT(a0)
        move.w  VBL,D_ACT(a0)
        tst.b   d1
        smi     d2                  ; sign of this step
        cmp.b   D_SIGN(a0),d2
        beq.s   .same
        move.b  d2,D_SIGN(a0)
        move.b  #1,D_RUN(a0)
        bra.s   .done
.same:  cmpi.b  #255,D_RUN(a0)
        beq.s   .run
        addq.b  #1,D_RUN(a0)
.run:   cmpi.b  #8,D_RUN(a0)        ; 8 small steps in a row the same way:
        bcs.s   .done               ; no pad does that
        st      D_DET(a0)
        bra.s   .done
.jump:  clr.b   D_RUN(a0)
.done:  rts

; =====================================================================
;  USER: the BIOS hands over here; we never give it back
; =====================================================================
user:
        move.w  #$2700,sr
        lea     $10f300,sp
        move.b  d0,REG_DIPSW
        move.b  d0,REG_SWPROM       ; cartridge vectors
        move.b  d0,REG_CRTFIX       ; cartridge fix tiles
        lea     RAM,a0
        move.w  #$100/4-1,d0
.clr:   clr.l   (a0)+
        dbra    d0,.clr
        bsr     init_video
        bsr     draw_static
        ; sample from the start: the first frame's reload, then every vblank
        move.w  #LSPC_BITS|$20,REG_LSPCMODE
        move.w  #0,REG_TIMERHIGH
        move.w  #TIMER_RELOAD,REG_TIMERLOW
        move.w  #LSPC_BITS,REG_LSPCMODE
        ori.b   #$80,BIOS_SYSTEM_MODE
        move.w  #$2000,sr
main:
        move.w  VBL,d0
.wait:  move.b  d0,REG_DIPSW
        cmp.w   VBL,d0
        beq.s   .wait
        bsr     update_pads
        bsr     update_spin
        bra.s   main

; =====================================================================
;  Video setup
; =====================================================================
init_video:
        ; hide every sprite (height 0)
        move.w  #$8200,REG_VRAMADDR
        move.w  #1,REG_VRAMMOD
        move.w  #$1ff,d0
.spr:   move.w  #0,REG_VRAMRW
        dbra    d0,.spr
        ; clear the fix layer to spaces
        move.w  #FIX,REG_VRAMADDR
        move.w  #40*32-1,d0
.fix:   move.w  #$0020,REG_VRAMRW
        dbra    d0,.fix
        move.w  #32,REG_VRAMMOD     ; text runs left to right
        ; palettes
        lea     palettes,a0
        lea     PALETTES,a1
        move.w  #8*16-1,d0
.pal:   move.w  (a0)+,(a1)+
        dbra    d0,.pal
        move.w  #$0012,BACKDROP
        rts

; d0.w = x, d1.w = y -> d0.w = fix address
fixaddr:
        lsl.w   #5,d0
        add.w   d1,d0
        addq.w  #2,d0               ; rows 0-1 are off screen
        addi.w  #FIX,d0
        rts

; a0 = string (0-terminated), d0 = x, d1 = y, d2 = palette bits
print:
        bsr.s   fixaddr
        move.w  d0,REG_VRAMADDR
        moveq   #0,d0
.ch:    move.b  (a0)+,d0
        beq.s   .end
        or.w    d2,d0
        move.w  d0,REG_VRAMRW
        moveq   #0,d0
        bra.s   .ch
.end:   rts

; d0 = x, d1 = y, d2 = palette bits: draw the pad map
draw_pad:
        lea     pad_map,a0
        move.w  d0,d3
        move.w  d1,d4
        moveq   #PAD_H-1,d6
.row:   move.w  d3,d0
        move.w  d4,d1
        bsr.s   fixaddr
        move.w  d0,REG_VRAMADDR
        moveq   #PAD_W-1,d5
.col:   move.w  (a0)+,d0
        cmpi.w  #$0020,d0           ; blank stays palette 0
        beq.s   .put
        or.w    d2,d0
.put:   move.w  d0,REG_VRAMRW
        dbra    d5,.col
        addq.w  #1,d4
        dbra    d6,.row
        rts

PADX1           equ 1
PADX2           equ 21
PADY            equ 4

draw_static:
        lea     s_title(pc),a0
        moveq   #3,d0
        moveq   #1,d1
        move.w  #P_HEAD,d2
        bsr     print
        lea     s_p1(pc),a0
        moveq   #PADX1+1,d0
        moveq   #PADY-1,d1
        move.w  #P_TEXT,d2
        bsr     print
        lea     s_p2(pc),a0
        moveq   #PADX2+1,d0
        moveq   #PADY-1,d1
        move.w  #P_TEXT,d2
        bsr     print
        moveq   #PADX1,d0
        moveq   #PADY,d1
        move.w  #1<<12,d2
        bsr     draw_pad
        moveq   #PADX2,d0
        moveq   #PADY,d1
        move.w  #2<<12,d2
        bsr     draw_pad
        lea     s_spin(pc),a0
        moveq   #1,d0
        moveq   #16,d1
        move.w  #P_HEAD,d2
        bsr     print
        ; labels in both columns
        moveq   #PADX1+1,d7
        bsr.s   .labels
        moveq   #PADX2+1,d7
.labels:
        lea     labels(pc),a1
.lab:   move.b  (a1)+,d1
        beq.s   .ldone
        ext.w   d1
        moveq   #0,d2
        move.b  (a1)+,d2
        lsl.w   #8,d2
        lsl.w   #4,d2
        move.l  a1,a0
        move.w  d7,d0
        bsr     print
        move.l  a0,a1
        bra.s   .lab
.ldone: rts

s_title:        dc.b    "NEO GEO PAD + SPINNER TEST",0
s_p1:           dc.b    "PLAYER 1",0
s_p2:           dc.b    "PLAYER 2",0
s_spin:         dc.b    "SPINNER  (TURN IT A FEW TIMES)",0
; {row, palette, text}
labels:
        dc.b    14,5,"INPUT",0
        dc.b    17,3,"JP3 ENCODER",0
        dc.b    19,5,"COUNT",0
        dc.b    20,5,"SPEED",0
        dc.b    21,5,"SKIP",0
        dc.b    23,3,"7-BIT DIAL",0
        dc.b    25,5,"POS",0
        dc.b    26,5,"COUNT",0
        dc.b    0
        even

; =====================================================================
;  Pads: light each part through its own palette entry
; =====================================================================
; element order matches the colour indices 4..14 in the pad art
update_pads:
        move.b  REG_STATUS_B,d4
        not.b   d4
        move.b  REG_STATUS_A,d5
        not.b   d5
        ; player 1
        move.b  REG_P1CNT,d0
        not.b   d0
        move.b  d4,d1               ; START bit0, SELECT bit1
        move.b  d5,d2               ; COIN bit0
        lea     PALETTES+1*32+4*2,a1
        bsr.s   .one
        ; player 2
        move.b  REG_P2CNT,d0
        not.b   d0
        move.b  d4,d1
        lsr.b   #2,d1               ; START bit2, SELECT bit3
        move.b  d5,d2
        lsr.b   #1,d2               ; COIN bit1
        lea     PALETTES+2*32+4*2,a1
.one:   lea     pad_dim(pc),a2
        lea     pad_lit(pc),a3
        moveq   #7,d3               ; UP DOWN LEFT RIGHT A B C D
.bit:   lsr.b   #1,d0
        bsr.s   .set
        dbra    d3,.bit
        lsr.b   #1,d1               ; START
        bsr.s   .set
        lsr.b   #1,d1               ; SELECT
        bsr.s   .set
        lsr.b   #1,d2               ; COIN
.set:   bcc.s   .dim
        move.w  (a3),(a1)+
        bra.s   .next
.dim:   move.w  (a2),(a1)+
.next:  addq.l  #2,a2
        addq.l  #2,a3
        rts

; =====================================================================
;  Spinner panel
; =====================================================================
update_spin:
        addq.w  #1,SPD_T
        lea     PL1,a5
        moveq   #PADX1+1,d7
        bsr.s   .one
        lea     PL2,a5
        moveq   #PADX2+1,d7
        bsr.s   .one
        cmpi.w  #15,SPD_T
        bcs.s   .r
        clr.w   SPD_T
.r:     rts
.one:
        ; speed, every 15 frames (x4 = per second)
        cmpi.w  #15,SPD_T
        bcs.s   .nos
        move.w  Q_CNT(a5),d0
        move.w  d0,d1
        sub.w   Q_SPD0(a5),d0
        move.w  d1,Q_SPD0(a5)
        lsl.w   #2,d0
        move.w  d0,Q_SPD(a5)
        move.w  PAIRS+Q_CNT(a5),d0
        move.w  d0,d1
        sub.w   PAIRS+Q_SPD0(a5),d0
        move.w  d1,PAIRS+Q_SPD0(a5)
        lsl.w   #2,d0
        move.w  d0,PAIRS+Q_SPD(a5)
        move.w  D_CNT(a5),d0
        move.w  d0,d1
        sub.w   D_SPD0(a5),d0
        move.w  d1,D_SPD0(a5)
        lsl.w   #2,d0
        move.w  d0,D_SPD(a5)
.nos:
        ; input bits UDLRABCD
        move.b  RAWA(a5),d4
        move.w  d7,d0
        addq.w  #6,d0
        moveq   #14,d1
        bsr     fixaddr
        move.w  d0,REG_VRAMADDR
        lea     s_bits(pc),a0
        moveq   #7,d3
.b:     move.w  #'.'|P_DIM,d0
        lsr.b   #1,d4
        bcc.s   .b0
        move.b  (a0),d0
        ori.w   #P_GOOD,d0
.b0:    move.w  d0,REG_VRAMRW
        addq.l  #1,a0
        dbra    d3,.b
        ; encoder: show the L/R wiring, or the pairs once only they are seen
        movea.l a5,a4
        lea     s_wlr(pc),a0
        tst.b   Q_DET(a5)
        bne.s   .w1
        tst.b   P_DET(a5)
        beq.s   .w0
        lea     PAIRS(a5),a4
        lea     s_wpairs(pc),a0
        bra.s   .w1
.w0:    lea     s_wnone(pc),a0
.w1:    move.w  d7,d0
        addi.w  #12,d0
        moveq   #17,d1
        move.w  #P_HEAD,d2
        bsr     print
        lea     s_det(pc),a0
        move.w  #P_GOOD,d2
        moveq   #0,d0
        move.b  Q_DET(a5),d0
        or.b    P_DET(a5),d0
        bne.s   .q1
        lea     s_none(pc),a0
        move.w  #P_DIM,d2
.q1:    move.w  d7,d0
        moveq   #18,d1
        bsr     print
        move.w  Q_ACT(a4),d0
        move.b  Q_DET(a5),d1        ; "MOVING" only once it's recognised
        or.b    P_DET(a5),d1
        bne.s   .qa
        moveq   #0,d0
.qa:    moveq   #18,d1
        bsr     act_flag
        move.w  Q_CNT(a4),d0
        moveq   #19,d1
        bsr     num_at
        move.w  Q_SPD(a4),d0
        moveq   #20,d1
        bsr     num_at
        move.w  Q_ERR(a4),d0
        moveq   #21,d1
        bsr     unum_at
        ; dial
        lea     s_det(pc),a0
        move.w  #P_GOOD,d2
        tst.b   D_DET(a5)
        bne.s   .d1
        lea     s_none(pc),a0
        move.w  #P_DIM,d2
.d1:    move.w  d7,d0
        moveq   #24,d1
        bsr     print
        move.w  D_ACT(a5),d0
        tst.b   D_DET(a5)
        bne.s   .da
        moveq   #0,d0
.da:    moveq   #24,d1
        bsr     act_flag
        moveq   #0,d0
        move.b  D_POS(a5),d0
        moveq   #25,d1
        bsr     unum_at
        move.w  D_CNT(a5),d0
        moveq   #26,d1
        bra     num_at

s_bits:         dc.b    "UDLRABCD"
s_det:          dc.b    "DETECTED",0
s_wlr:          dc.b    "L/R  ",0
s_wpairs:       dc.b    "PAIRS",0
s_wnone:        dc.b    "     ",0
s_none:         dc.b    "NOT SEEN",0
s_on:           dc.b    "MOVING",0
s_off:          dc.b    "      ",0
        even

; d0.w = VBL of the last step, d1 = row: "MOVING" for half a second after it
act_flag:
        move.w  VBL,d2
        sub.w   d0,d2
        lea     s_on(pc),a0
        cmpi.w  #30,d2
        bcs.s   .on
        lea     s_off(pc),a0
.on:    tst.w   d0
        bne.s   .p
        lea     s_off(pc),a0
.p:     move.w  d7,d0
        addi.w  #10,d0
        move.w  #P_HEAD,d2
        bra     print

; signed number d0.w at column d7+6, row d1: "+01234"
num_at:
        lea     numbuf,a0
        move.b  #'+',(a0)
        tst.w   d0
        bpl.s   .p
        move.b  #'-',(a0)
        neg.w   d0
.p:     addq.l  #1,a0
        bsr.s   dec5
        lea     numbuf,a0
        bra.s   put_num
; unsigned d0.w: " 01234"
unum_at:
        lea     numbuf,a0
        move.b  #' ',(a0)+
        bsr.s   dec5
        lea     numbuf,a0
put_num:
        move.w  d7,d0
        addq.w  #6,d0
        move.w  #P_TEXT,d2
        bra     print

; d0.w (0..65535) -> 5 digits at a0, 0-terminated
dec5:
        andi.l  #$ffff,d0
        lea     5(a0),a1
        clr.b   (a1)
        moveq   #4,d2
.d:     divu    #10,d0
        swap    d0
        addi.b  #'0',d0
        move.b  d0,-(a1)
        clr.w   d0
        swap    d0
        dbra    d2,.d
        rts

numbuf          equ RAM+$20

; ---- colours (Neo Geo format) ----
; element order: UP DOWN LEFT RIGHT A B C D START SELECT COIN
pad_dim:
        dc.w    $0222,$0222,$0222,$0222     ; d-pad
        dc.w    $0611,$0651,$0252,$0237     ; A red, B yellow, C green, D blue
        dc.w    $0333,$0333                 ; START, SELECT
        dc.w    $0541                       ; COIN
pad_lit:
        dc.w    $7ffd,$7ffd,$7ffd,$7ffd
        dc.w    $7f44,$7fd4,$75e6,$759f
        dc.w    $7fff,$7fff
        dc.w    $7fc3

palettes:
        ; 0: unused (blank tiles)
        dc.w    $0000,$0000,$0000,$0000,$0000,$0000,$0000,$0000
        dc.w    $0000,$0000,$0000,$0000,$0000,$0000,$0000,$0000
        ; 1, 2: the pads (entries 4..14 rewritten every frame)
        rept    2
        dc.w    $0000,$0111,$0334,$0445,$0222,$0222,$0222,$0222
        dc.w    $0611,$0651,$0252,$0237,$0333,$0333,$0541,$0ccd
        endr
        ; 3: text
        dc.w    $0000,$7eef,$0000,$0000,$0000,$0000,$0000,$0000
        dc.w    $0000,$0000,$0000,$0000,$0000,$0000,$0000,$0000
        ; 4: good (green)
        dc.w    $0000,$45e7,$0000,$0000,$0000,$0000,$0000,$0000
        dc.w    $0000,$0000,$0000,$0000,$0000,$0000,$0000,$0000
        ; 5: dim
        dc.w    $0000,$0778,$0000,$0000,$0000,$0000,$0000,$0000
        dc.w    $0000,$0000,$0000,$0000,$0000,$0000,$0000,$0000
        ; 6: heading (gold)
        dc.w    $0000,$7fc3,$0000,$0000,$0000,$0000,$0000,$0000
        dc.w    $0000,$0000,$0000,$0000,$0000,$0000,$0000,$0000
        ; 7: bad (red)
        dc.w    $0000,$7f55,$0000,$0000,$0000,$0000,$0000,$0000
        dc.w    $0000,$0000,$0000,$0000,$0000,$0000,$0000,$0000

        include "gfx.inc"           ; generated into build/ by tools/mkgfx.py

        ; pad the P ROM to 1 MB in the build script
