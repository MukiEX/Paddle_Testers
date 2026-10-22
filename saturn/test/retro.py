"""Minimal ctypes libretro frontend for the yabause core (with dbg_* hooks).

Scripted input per port: joypad button set, mouse dX/dY + buttons, analog X (wheel / 3D pad).
"""
import ctypes as C, os, sys
from PIL import Image
import numpy as np

CORE = os.environ.get('YAB_CORE', os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'third_party', 'yabause_libretro.so'))
SYSDIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sys')
os.makedirs(SYSDIR, exist_ok=True)

# libretro ids
DEV_JOYPAD, DEV_MOUSE, DEV_ANALOG = 1, 2, 5
DEV_3DPAD = 5
DEV_WHEEL = (1 << 8) | 5
JP = dict(B=0, Y=1, SELECT=2, START=3, UP=4, DOWN=5, LEFT=6, RIGHT=7, A=8, X=9, L=10, R=11, L2=12, R2=13)
# Saturn button -> libretro joypad id (per libretro.c mapping)
SAT = dict(A='B', B='A', C='R', X='Y', Y='X', Z='L', START='START', UP='UP', DOWN='DOWN', LEFT='LEFT', RIGHT='RIGHT', L='L2', R='R2')

class GameInfo(C.Structure):
    _fields_ = [('path', C.c_char_p), ('data', C.c_void_p), ('size', C.c_size_t), ('meta', C.c_char_p)]
class Var(C.Structure):
    _fields_ = [('key', C.c_char_p), ('value', C.c_char_p)]

ENV_CB = C.CFUNCTYPE(C.c_bool, C.c_uint, C.c_void_p)
VID_CB = C.CFUNCTYPE(None, C.c_void_p, C.c_uint, C.c_uint, C.c_size_t)
AUD_CB = C.CFUNCTYPE(None, C.c_int16, C.c_int16)
AUDB_CB = C.CFUNCTYPE(C.c_size_t, C.c_void_p, C.c_size_t)
POLL_CB = C.CFUNCTYPE(None)
STATE_CB = C.CFUNCTYPE(C.c_int16, C.c_uint, C.c_uint, C.c_uint, C.c_uint)
LOG_CB = C.CFUNCTYPE(None, C.c_int, C.c_char_p)
DBG_CB = C.CFUNCTYPE(None, C.c_uint32, C.POINTER(C.c_uint32))

class Port:
    def __init__(s):
        s.buttons = set(); s.mx = 0; s.my = 0; s.mbtn = set(); s.ax = 0; s.ay = 0

class Retro:
    def __init__(s, cue, variables=None, log=False):
        s.lib = C.CDLL(CORE)
        s.vars = {b'yabause_frameskip': b'disabled', b'yabause_addon_cartridge': b'none',
                  b'yabause_multitap_port1': b'disabled', b'yabause_multitap_port2': b'disabled'}
        if variables: s.vars.update(variables)
        s._keep = []
        s.ports = [Port(), Port()]
        s.frame = None; s.fw = s.fh = 0
        s.log = log
        s.bp_handlers = {}
        lib = s.lib
        s._env = ENV_CB(s._env_cb); s._vid = VID_CB(s._vid_cb); s._aud = AUD_CB(lambda l, r: None)
        s._audb = AUDB_CB(lambda d, n: n); s._poll = POLL_CB(lambda: None); s._state = STATE_CB(s._state_cb)
        s._log = LOG_CB(s._log_cb)
        s._dbg = DBG_CB(s._dbg_cb)
        lib.retro_set_environment(s._env)
        lib.retro_set_video_refresh(s._vid); lib.retro_set_audio_sample(s._aud); lib.retro_set_audio_sample_batch(s._audb)
        lib.retro_set_input_poll(s._poll); lib.retro_set_input_state(s._state)
        lib.retro_init()
        gi = GameInfo(os.path.abspath(cue).encode(), None, 0, None)
        assert lib.retro_load_game(C.byref(gi)), 'load failed'
        lib.dbg_set_cb(s._dbg)
        lib.dbg_r8.restype = C.c_uint8; lib.dbg_r16.restype = C.c_uint16; lib.dbg_r32.restype = C.c_uint32
        lib.dbg_pc.restype = C.c_uint32
        lib.retro_serialize_size.restype = C.c_size_t
        s.devices = [None, None]
        s.set_device(0, DEV_JOYPAD); s.set_device(1, DEV_JOYPAD)

    # ---------------- callbacks
    def _log_cb(s, lvl, msg):
        if s.log: sys.stdout.write('[core] ' + msg.decode(errors='replace'))
    def _env_cb(s, cmd, data):
        if cmd == 15:  # GET_VARIABLE
            v = C.cast(data, C.POINTER(Var)).contents
            if v.key in s.vars:
                buf = C.c_char_p(s.vars[v.key]); s._keep.append(buf); v.value = buf.value; return True
            return False
        if cmd == 9 or cmd == 31:  # SYSTEM / SAVE directory
            p = C.c_char_p(SYSDIR.encode()); s._keep.append(p)
            C.cast(data, C.POINTER(C.c_char_p))[0] = p.value; return True
        if cmd == 10: return True   # SET_PIXEL_FORMAT
        if cmd == 27:  # GET_LOG_INTERFACE
            C.cast(data, C.POINTER(C.c_void_p))[0] = C.cast(s._log, C.c_void_p).value; return True
        if cmd == 51: return True  # input bitmasks
        if cmd == 17:  # GET_VARIABLE_UPDATE
            C.cast(data, C.POINTER(C.c_bool))[0] = False; return True
        return False
    def _vid_cb(s, data, w, h, pitch):
        if data:
            s.fw, s.fh = w, h
            s.frame = C.string_at(data, pitch * h); s.pitch = pitch
    def _state_cb(s, port, device, index, id_):
        if port > 1: return 0
        p = s.ports[port]
        if device == DEV_JOYPAD:
            if id_ == 256:
                m = 0
                for b in p.buttons: m |= 1 << JP[SAT[b]]
                return m
            return int(any(JP[SAT[b]] == id_ for b in p.buttons))
        if device == DEV_MOUSE:
            if id_ == 0: return p.mx
            if id_ == 1: return p.my
            if id_ == 2: return int('LEFT' in p.mbtn)
            if id_ == 3: return int('RIGHT' in p.mbtn)
            if id_ == 6: return int('MIDDLE' in p.mbtn)
            return 0
        if device == DEV_ANALOG:
            if index == 0 and id_ == 0: return p.ax
            if index == 0 and id_ == 1: return p.ay
            return 0
        return 0
    def _dbg_cb(s, pc, regs):
        h = s.bp_handlers.get(pc)
        if h: h(regs)

    # ---------------- API
    def set_device(s, port, dev):
        s.devices[port] = dev
        s.lib.retro_set_controller_port_device(port, dev)
    def run(s, n=1, mouse=None):
        for _ in range(n):
            s.lib.retro_run()
            for p in s.ports: p.mx = p.my = 0  # mouse deltas are per frame
    def r8(s, a): return s.lib.dbg_r8(a)
    def r16(s, a): return s.lib.dbg_r16(a)
    def r32(s, a): return s.lib.dbg_r32(a)
    def w8(s, a, v): s.lib.dbg_w8(a, v)
    def w16(s, a, v): s.lib.dbg_w16(a, v)
    def w32(s, a, v): s.lib.dbg_w32(a, v)
    def read(s, a, n):
        b = C.create_string_buffer(n); s.lib.dbg_read(a, b, n); return b.raw
    def write(s, a, data): s.lib.dbg_write(a, data, len(data))
    def bp(s, addr, fn):
        s.bp_handlers[addr] = fn; s.lib.dbg_add_bp(addr)
    def clear_bp(s):
        s.bp_handlers = {}; s.lib.dbg_clear_bp()
    def save_state(s):
        n = s.lib.retro_serialize_size(); b = C.create_string_buffer(n)
        assert s.lib.retro_serialize(b, n); return b.raw
    def load_state(s, data):
        b = C.create_string_buffer(data, len(data)); assert s.lib.retro_unserialize(b, len(data))
    def screenshot(s, path):
        a = np.frombuffer(s.frame, dtype=np.uint16).reshape(s.fh, s.pitch // 2)[:, :s.fw]
        r = ((a >> 11) & 31) << 3; g = ((a >> 5) & 63) << 2; b = (a & 31) << 3
        Image.fromarray(np.dstack([r, g, b]).astype(np.uint8)).save(path)
    def press(s, port, btns, frames=3, after=10):
        s.ports[port].buttons |= set(btns); s.run(frames)
        s.ports[port].buttons -= set(btns); s.run(after)

def coverage(r, frames):
    import ctypes as C
    cov = (C.c_ubyte * 0x80000).in_dll(r.lib, 'dbg_cov')
    C.memset(cov, 0, 0x80000)
    r.lib.dbg_cov_enable(1); r.run(frames); r.lib.dbg_cov_enable(0)
    a = np.frombuffer(bytes(cov), dtype=np.uint8)
    return set((0x06000000 + 2 * i) for i in np.nonzero(a)[0])

def ranges(addrs, gap=4):
    out = []; 
    for a in sorted(addrs):
        if out and a - out[-1][1] <= gap: out[-1][1] = a
        else: out.append([a, a])
    return out

def watch(r, lo, hi, frames, step=None):
    """Run frames with a write watchpoint; returns list of (pc, addr, val, size, pr)."""
    import ctypes as C
    r.lib.dbg_watch(lo, hi)
    if step: step()
    else: r.run(frames)
    n = C.c_int.in_dll(r.lib, 'dbg_wn').value
    log = (C.c_uint32 * (4096 * 4)).in_dll(r.lib, 'dbg_wlog')
    out = [(log[i*4], log[i*4+1], log[i*4+2], log[i*4+3] & 3, log[i*4+3] & ~3) for i in range(n)]
    r.lib.dbg_watch(1, 0)
    return out
