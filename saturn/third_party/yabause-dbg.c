/* Debug hooks for the MD3 Saturn paddle project test harness */
#include <string.h>
#include "../sh2core.h"
#include "../memory.h"
#include "../yabause.h"
extern SH2_struct *MSH2, *SSH2;
typedef void (*dbg_cb_t)(u32 pc, u32 *regs);
static dbg_cb_t dbg_cb;
#define MAXBP 64
static u32 bps[MAXBP]; static int nbp;
unsigned char dbg_cov[0x80000];   /* one byte per halfword of 0x06000000-0x060FFFFF */
int dbg_cov_on;
int dbg_hook_active;
void dbg_exec_hook(SH2_struct *c)
{
   u32 pc = c->regs.PC;
   if (c != MSH2) return;
   if (dbg_cov_on && (pc & 0x0FF00000) == 0x06000000) dbg_cov[(pc & 0xFFFFF) >> 1] = 1;
   for (int i = 0; i < nbp; i++) if (bps[i] == pc) {
      u32 r[20]; memcpy(r, c->regs.R, 64); r[16] = c->regs.PR; r[17] = c->regs.SR.all; r[18] = c->regs.GBR; r[19] = pc;
      if (dbg_cb) dbg_cb(pc, r);
      memcpy(c->regs.R, r, 64); c->regs.PR = r[16];
      if (r[19] != pc) c->regs.PC = r[19];
      break;
   }
}
static void upd(void){ dbg_hook_active = dbg_cov_on || nbp; }
void dbg_set_cb(dbg_cb_t f){ dbg_cb = f; }
void dbg_add_bp(u32 a){ if (nbp < MAXBP) bps[nbp++] = a; upd(); }
void dbg_clear_bp(void){ nbp = 0; upd(); }
void dbg_cov_enable(int on){ dbg_cov_on = on; upd(); }
u8 dbg_r8(u32 a){ return MappedMemoryReadByteNocache(MSH2, a); }
u16 dbg_r16(u32 a){ return MappedMemoryReadWordNocache(MSH2, a); }
u32 dbg_r32(u32 a){ return MappedMemoryReadLongNocache(MSH2, a); }
void dbg_w8(u32 a, u8 v){ MappedMemoryWriteByteNocache(MSH2, a, v); }
void dbg_w16(u32 a, u16 v){ MappedMemoryWriteWordNocache(MSH2, a, v); }
void dbg_w32(u32 a, u32 v){ MappedMemoryWriteLongNocache(MSH2, a, v); }
void dbg_read(u32 a, u8 *buf, u32 n){ for (u32 i = 0; i < n; i++) buf[i] = MappedMemoryReadByteNocache(MSH2, a + i); }
void dbg_write(u32 a, const u8 *buf, u32 n){ for (u32 i = 0; i < n; i++) MappedMemoryWriteByteNocache(MSH2, a + i, buf[i]); }
u32 dbg_pc(void){ return MSH2->regs.PC; }

/* ---- write watchpoints: records (pc, addr, val, size) of writes into [wlo, whi) */
static writebytefunc ow8; static writewordfunc ow16; static writelongfunc ow32;
static u32 wlo, whi;
#define WMAX 4096
u32 dbg_wlog[WMAX][4]; int dbg_wn;
static void rec(SH2_struct *sh, u32 a, u32 v, u32 sz){
   if (((a & 0x0FFFFFFF) >= wlo) && ((a & 0x0FFFFFFF) < whi) && dbg_wn < WMAX) {
      dbg_wlog[dbg_wn][0] = sh->regs.PC; dbg_wlog[dbg_wn][1] = a; dbg_wlog[dbg_wn][2] = v; dbg_wlog[dbg_wn][3] = sz | (sh->regs.PR & ~3u) ; dbg_wn++; }
}
static void FASTCALL ww8(SH2_struct *sh, u32 a, u8 v){ rec(sh,a,v,1); ow8(sh,a,v); }
static void FASTCALL ww16(SH2_struct *sh, u32 a, u16 v){ rec(sh,a,v,2); ow16(sh,a,v); }
static void FASTCALL ww32(SH2_struct *sh, u32 a, u32 v){ rec(sh,a,v,0); ow32(sh,a,v); }
void dbg_watch(u32 lo, u32 hi){
   if (!ow8) { ow8 = MSH2->MappedMemoryWriteByte; ow16 = MSH2->MappedMemoryWriteWord; ow32 = MSH2->MappedMemoryWriteLong; }
   wlo = lo & 0x0FFFFFFF; whi = hi & 0x0FFFFFFF; dbg_wn = 0;
   if (lo < hi) { MSH2->MappedMemoryWriteByte = ww8; MSH2->MappedMemoryWriteWord = ww16; MSH2->MappedMemoryWriteLong = ww32; }
   else { MSH2->MappedMemoryWriteByte = ow8; MSH2->MappedMemoryWriteWord = ow16; MSH2->MappedMemoryWriteLong = ow32; }
}

/* ---- write bitmap: one byte per 16 bytes of high WRAM (0x06000000) and low WRAM (0x00200000) */
unsigned char dbg_wmap_hi[0x10000], dbg_wmap_lo[0x10000];
static void FASTCALL mw8(SH2_struct *sh, u32 a, u8 v);
static void FASTCALL mw16(SH2_struct *sh, u32 a, u16 v);
static void FASTCALL mw32(SH2_struct *sh, u32 a, u32 v);
static inline void mark(u32 a){ a &= 0x0FFFFFFF; if ((a & 0x0FF00000) == 0x06000000) dbg_wmap_hi[(a & 0xFFFFF) >> 4] = 1; else if ((a & 0x0FF00000) == 0x00200000) dbg_wmap_lo[(a & 0xFFFFF) >> 4] = 1; }
static void FASTCALL mw8(SH2_struct *sh, u32 a, u8 v){ mark(a); ow8(sh,a,v); }
static void FASTCALL mw16(SH2_struct *sh, u32 a, u16 v){ mark(a); ow16(sh,a,v); }
static void FASTCALL mw32(SH2_struct *sh, u32 a, u32 v){ mark(a); ow32(sh,a,v); }
void dbg_wmap(int on){
   if (!ow8) { ow8 = MSH2->MappedMemoryWriteByte; ow16 = MSH2->MappedMemoryWriteWord; ow32 = MSH2->MappedMemoryWriteLong; }
   if (on) { MSH2->MappedMemoryWriteByte = mw8; MSH2->MappedMemoryWriteWord = mw16; MSH2->MappedMemoryWriteLong = mw32; }
   else { MSH2->MappedMemoryWriteByte = ow8; MSH2->MappedMemoryWriteWord = ow16; MSH2->MappedMemoryWriteLong = ow32; }
}
