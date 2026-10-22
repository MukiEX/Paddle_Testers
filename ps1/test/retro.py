import ctypes as C, os, sys
from PIL import Image
import numpy as np
import os
from env import ROOT, CORE
class GameInfo(C.Structure): _fields_=[('path',C.c_char_p),('data',C.c_void_p),('size',C.c_size_t),('meta',C.c_char_p)]
class Var(C.Structure): _fields_=[('key',C.c_char_p),('value',C.c_char_p)]
ENVCB=C.CFUNCTYPE(C.c_bool,C.c_uint,C.c_void_p)
VIDCB=C.CFUNCTYPE(None,C.c_void_p,C.c_uint,C.c_uint,C.c_size_t)
ASCB=C.CFUNCTYPE(None,C.c_int16,C.c_int16)
ABCB=C.CFUNCTYPE(C.c_size_t,C.c_void_p,C.c_size_t)
IPCB=C.CFUNCTYPE(None)
ISCB=C.CFUNCTYPE(C.c_int16,C.c_uint,C.c_uint,C.c_uint,C.c_uint)
# joypad ids
B,Y,SELECT,START,UP,DOWN,LEFT,RIGHT,A,X,L,R,L2,R2=0,1,2,3,4,5,6,7,8,9,10,11,12,13
class Emu:
    def __init__(s,cue,opts=None,ports=('standard','standard')):
        s.lib=C.CDLL(CORE)
        s.opts={'pcsx_rearmed_drc':'disabled','pcsx_rearmed_bios':'auto','pcsx_rearmed_region':'auto',
                'pcsx_rearmed_show_bios_bootlogo':'disabled','pcsx_rearmed_frameskip_type':'disabled'}
        if opts: s.opts.update(opts)
        s._keep=[]; s.pad=[set(),set()]; s.mouse=[[0,0,0,0],[0,0,0,0]]; s.analog=[[0,0,0,0],[0,0,0,0]]
        s.frame=None; s.fmt=1; s.nframes=0
        s.sysdir=C.c_char_p((ROOT+'/sys').encode())
        s.envcb=ENVCB(s._env); s.vidcb=VIDCB(s._vid); s.ascb=ASCB(lambda l,r:None); s.abcb=ABCB(lambda d,n:n)
        s.ipcb=IPCB(lambda:None); s.iscb=ISCB(s._in)
        L=s.lib
        L.retro_set_environment(s.envcb); L.retro_set_video_refresh(s.vidcb); L.retro_set_audio_sample(s.ascb)
        L.retro_set_audio_sample_batch(s.abcb); L.retro_set_input_poll(s.ipcb); L.retro_set_input_state(s.iscb)
        L.retro_init()
        gi=GameInfo(cue.encode(),None,0,None)
        assert L.retro_load_game(C.byref(gi)), 'load failed'
        L.retro_get_memory_data.restype=C.c_void_p; L.retro_get_memory_size.restype=C.c_size_t
        devmap={'standard':0x101 ,'mouse':0x102,'negcon':0x305,'dualshock':0x205,'analog':0x105,'none':0}
        # RETRO_DEVICE_SUBCLASS(base,id)=((id+1)<<8)|base ; joypad=1 analog=5 mouse=2
        for p,t in enumerate(ports): L.retro_set_controller_port_device(p,devmap[t])
        s.ports=ports
        s.ram=(C.c_uint8*0x200000).from_address(L.retro_get_memory_data(2))
    def _env(s,cmd,data):
        cmd&=0xFFFF
        if cmd==9 or cmd==31:
            C.cast(data,C.POINTER(C.c_char_p))[0]=s.sysdir.value; return True
        if cmd==10: s.fmt=C.cast(data,C.POINTER(C.c_int))[0]; return True
        if cmd==15:
            v=C.cast(data,C.POINTER(Var))[0]; k=v.key.decode()
            if k in s.opts:
                b=C.c_char_p(s.opts[k].encode()); s._keep.append(b); C.cast(data,C.POINTER(Var))[0].value=b.value; return True
            return False
        if cmd==52: C.cast(data,C.POINTER(C.c_uint))[0]=0; return True
        if cmd==3: C.cast(data,C.POINTER(C.c_bool))[0]=True; return True
        return False
    def _vid(s,data,w,h,pitch):
        if not data: return
        if s.fmt==1:
            a=np.ctypeslib.as_array((C.c_uint8*(pitch*h)).from_address(data)).reshape(h,pitch)[:,:w*4].reshape(h,w,4)
            s.frame=a[:,:,2::-1].copy()
        else:
            a=np.ctypeslib.as_array((C.c_uint16*(pitch//2*h)).from_address(data)).reshape(h,pitch//2)[:,:w]
            r=((a>>11)&31)<<3; g=((a>>5)&63)<<2; b=(a&31)<<3
            s.frame=np.dstack([r,g,b]).astype(np.uint8)
    def _in(s,port,dev,idx,id):
        if port>1: return 0
        if dev==1:
            if id==256: return sum(1<<b for b in s.pad[port])
            return 1 if id in s.pad[port] else 0
        if dev==2:
            m=s.mouse[port]
            if id==0: v=m[0]; return v
            if id==1: return m[1]
            if id==2: return m[2]
            if id==3: return m[3]
            return 0
        if dev==5:
            return s.analog[port][idx*2+id] if idx<2 and id<2 else 0
        return 0
    def run(s,n=1):
        for i in range(n):
            s.lib.retro_run(); s.nframes+=1
            s.mouse[0][0]=s.mouse[0][1]=s.mouse[1][0]=s.mouse[1][1]=0
    def press(s,port,btn,hold=3,after=8):
        s.pad[port].add(btn); s.run(hold); s.pad[port].discard(btn); s.run(after)
    def shot(s,path):
        Image.fromarray(s.frame).save(path)
    def r8(s,a): return s.ram[a&0x1FFFFF]
    def r16(s,a): a&=0x1FFFFF; return s.ram[a]|s.ram[a+1]<<8
    def r32(s,a): a&=0x1FFFFF; return s.ram[a]|s.ram[a+1]<<8|s.ram[a+2]<<16|s.ram[a+3]<<24
    def rb(s,a,n): a&=0x1FFFFF; return bytes(s.ram[a:a+n])
    def save(s):
        n=s.lib.retro_serialize_size(); buf=(C.c_uint8*n)(); assert s.lib.retro_serialize(buf,n); return bytes(buf)
    def load(s,data):
        buf=(C.c_uint8*len(data)).from_buffer_copy(data); assert s.lib.retro_unserialize(buf,len(data))

WCB=C.CFUNCTYPE(None,C.c_void_p,C.c_uint32,C.c_uint32,C.c_uint32,C.c_int)
RCB=C.CFUNCTYPE(None,C.c_void_p,C.c_uint32,C.c_uint32,C.c_int)
BCB=C.CFUNCTYPE(None,C.c_void_p,C.c_uint32)
def _regs(p): return list((C.c_uint32*34).from_address(p))
def watch_w(e,lo,size,fn):
    """fn(regs,pc,addr,val,size)"""
    e._wcb=WCB(lambda r,pc,a,v,s: fn(_regs(r),pc,a,v,s))
    C.c_uint32.in_dll(e.lib,'retro_dbg_wlo').value=lo&0x1fffffff
    C.c_uint32.in_dll(e.lib,'retro_dbg_wsize').value=size
    C.c_void_p.in_dll(e.lib,'retro_dbg_wcb').value=C.cast(e._wcb,C.c_void_p).value
def watch_r(e,lo,size,fn):
    e._rcb=RCB(lambda r,pc,a,s: fn(_regs(r),pc,a,s))
    C.c_uint32.in_dll(e.lib,'retro_dbg_rlo').value=lo&0x1fffffff
    C.c_uint32.in_dll(e.lib,'retro_dbg_rsize').value=size
    C.c_void_p.in_dll(e.lib,'retro_dbg_rcb').value=C.cast(e._rcb,C.c_void_p).value
def unwatch(e):
    C.c_void_p.in_dll(e.lib,'retro_dbg_wcb').value=None; C.c_void_p.in_dll(e.lib,'retro_dbg_rcb').value=None
def bp(e,addrs,fn):
    m=(C.c_uint32*16384).in_dll(e.lib,'retro_dbg_bpmap')
    for i in range(16384): m[i]=0
    for a in addrs:
        i=(a&0x1ffffc)>>2; m[i>>5]|=1<<(i&31)
    e._bcb=BCB(lambda r,pc: fn(_regs(r),pc))
    C.c_void_p.in_dll(e.lib,'retro_dbg_bpcb').value=C.cast(e._bcb,C.c_void_p).value
RN=['zero','at','v0','v1','a0','a1','a2','a3','t0','t1','t2','t3','t4','t5','t6','t7','s0','s1','s2','s3','s4','s5','s6','s7','t8','t9','k0','k1','gp','sp','fp','ra']
class Cov:
    def __init__(s,e):
        s.e=e; s.m=(C.c_uint32*16384).in_dll(e.lib,'retro_dbg_wmap')
        s.prev=np.frombuffer(e.rb(0x80000000,0x200000),dtype=np.uint8).copy()
        s.chg=np.zeros(0x200000,dtype=bool)
    def tick(s):
        cur=np.frombuffer(s.e.rb(0x80000000,0x200000),dtype=np.uint8)
        s.chg|=cur!=s.prev; s.prev=cur.copy()
    def run(s,n,every=2):
        for i in range(n):
            s.e.run(1)
            if i%every==0: s.tick()
    def words(s):
        w=np.ctypeslib.as_array(s.m).copy()
        bits=np.unpackbits(w.view(np.uint8),bitorder='little').astype(bool)  # per word
        b=np.repeat(bits,4)
        return b|s.chg
def xmap(e):
    m=(C.c_uint32*16384).in_dll(e.lib,'retro_dbg_xmap')
    w=np.ctypeslib.as_array(m).copy()
    return np.unpackbits(w.view(np.uint8),bitorder='little').astype(bool)  # per instruction word
