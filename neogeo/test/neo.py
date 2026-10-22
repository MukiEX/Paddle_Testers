"""Headless Neo Geo harness around a patched Geolith libretro core.

Inputs are sampled by the core on every read of REG_P1CNT/P2CNT, and this
harness answers using the emulated time inside the frame, so quadrature
signals can toggle many times per frame exactly like a real encoder.
"""
import ctypes as C, os, struct

# Patched Geolith core (see geolith-harness.patch) and a folder holding neogeo.zip
CORE = os.environ.get('GEOLITH_CORE', 'geolith_libretro.so')
SYSDIR = os.environ.get('NEOGEO_SYSDIR', 'sys')
MCYC_PER_FRAME = 405504
MCYC_PER_LINE = 1536

# libretro joypad ids
UP, DOWN, LEFT, RIGHT = 4, 5, 6, 7
BTN = {'A': 0, 'B': 8, 'C': 1, 'D': 9, 'SELECT': 2, 'START': 3,
       'UP': UP, 'DOWN': DOWN, 'LEFT': LEFT, 'RIGHT': RIGHT, 'L3': 14, 'R3': 15}


class GameInfo(C.Structure):
    _fields_ = [('path', C.c_char_p), ('data', C.c_void_p), ('size', C.c_size_t), ('meta', C.c_char_p)]


class Var(C.Structure):
    _fields_ = [('key', C.c_char_p), ('value', C.c_char_p)]


ENV_CB = C.CFUNCTYPE(C.c_bool, C.c_uint, C.c_void_p)
VIDEO_CB = C.CFUNCTYPE(None, C.c_void_p, C.c_uint, C.c_uint, C.c_size_t)
AUDIO_CB = C.CFUNCTYPE(None, C.c_int16, C.c_int16)
AUDIOB_CB = C.CFUNCTYPE(C.c_size_t, C.c_void_p, C.c_size_t)
POLL_CB = C.CFUNCTYPE(None)
STATE_CB = C.CFUNCTYPE(C.c_int16, C.c_uint, C.c_uint, C.c_uint, C.c_uint)


class Spinner:
    """Quadrature encoder on LEFT (phase A) / RIGHT (phase B).

    rate: counts per second (signed; + = 'right'/clockwise).
    quantum_us: the input path only updates every N microseconds (MiSTer USB ~1000).
    """
    def __init__(self):
        self.pos = 0.0
        self.rate = 0.0
        self.t0 = 0
        self.quantum = 0
        self.invert = False

    def phase(self, t_mcyc):
        # 24 MHz master clock
        t = t_mcyc
        if self.quantum:
            q = int(self.quantum * 24)  # us -> mcyc
            t = (t // q) * q
        p = self._raw(t)
        g = [(0, 0), (1, 0), (1, 1), (0, 1)][p & 3]
        return (g[1], g[0]) if self.invert else g

    def _raw(self, t):
        x = self.pos + self.rate * (t - self.t0) / 24e6
        tg = getattr(self, 'target', None)
        if tg is not None:
            x = min(x, tg) if self.rate > 0 else max(x, tg) if self.rate < 0 else x
        import math
        return math.floor(x)

    def set_rate(self, now, rate):
        self.pos = self._raw(now) if self.rate else self.pos
        self.t0 = now
        self.rate = rate

    def count(self, now):
        return self._raw(now)


class Neo:
    def __init__(self, neo_path, system='mvs', region='eu', vars_extra=None):
        self.lib = C.CDLL(CORE)
        defaults = dict(geolith_unibios_hw='mvs', geolith_memcard='off', geolith_memcard_wp='off',
                        geolith_settingmode='off', geolith_4player='off', geolith_freeplay='off',
                        geolith_overscan_t='8', geolith_overscan_b='8', geolith_overscan_l='8',
                        geolith_overscan_r='8', geolith_palette='resnet', geolith_aspect='1:1',
                        geolith_sprlimit='96', geolith_oc='off', geolith_disable_adpcm_wrap='off',
                        geolith_system_type=system, geolith_region=region)
        self.vars = {k.encode(): v.encode() for k, v in defaults.items()}
        if vars_extra:
            self.vars.update({k.encode(): v.encode() for k, v in vars_extra.items()})
        self._keep = []
        self.frame_no = 0
        self.held = [set(), set()]
        self.spin = [Spinner(), Spinner()]
        self.spin_on = [False, False]
        self.fb = None
        self.fbw = self.fbh = self.fbpitch = 0
        self.pixfmt = 0
        self.reads = [0, 0]
        self._sysdir = C.c_char_p(SYSDIR.encode())
        self._savedir = C.c_char_p(SYSDIR.encode())
        self._varstore = {}

        self._env = ENV_CB(self.env)
        self._video = VIDEO_CB(self.video)
        self._audio = AUDIO_CB(lambda l, r: None)
        self._audiob = AUDIOB_CB(lambda d, n: n)
        self._poll = POLL_CB(lambda: None)
        self._state = STATE_CB(self.state)
        L = self.lib
        L.retro_set_environment(self._env)
        L.retro_set_video_refresh(self._video)
        L.retro_set_audio_sample(self._audio)
        L.retro_set_audio_sample_batch(self._audiob)
        L.retro_set_input_poll(self._poll)
        L.retro_set_input_state(self._state)
        L.retro_init()
        data = open(neo_path, 'rb').read()
        self._data = C.create_string_buffer(data, len(data))
        gi = GameInfo(neo_path.encode(), C.cast(self._data, C.c_void_p), len(data), None)
        L.retro_load_game.restype = C.c_bool
        if not L.retro_load_game(C.byref(gi)):
            raise RuntimeError('load failed')
        L.geo_dbg_mcycs.restype = C.c_uint32
        L.geo_m68k_ram_ptr.restype = C.c_void_p
        self.ram = (C.c_uint8 * 0x10000).from_address(L.geo_m68k_ram_ptr())
        L.m68k_get_reg.restype = C.c_uint
        L.m68k_get_reg.argtypes = [C.c_void_p, C.c_int]

    # ---- callbacks
    def env(self, cmd, data):
        cmd &= 0xffff
        if cmd in (9, 31):  # system / save directory
            C.cast(data, C.POINTER(C.c_char_p))[0] = SYSDIR.encode()
            return True
        if cmd == 15:  # GET_VARIABLE
            v = C.cast(data, C.POINTER(Var))[0]
            val = self.vars.get(v.key)
            if val is None:
                return False
            buf = self._varstore.setdefault(v.key, C.c_char_p(val))
            C.cast(data, C.POINTER(Var))[0].value = buf.value
            return True
        if cmd == 10:
            self.pixfmt = C.cast(data, C.POINTER(C.c_int))[0]
            return True
        if cmd == 3:  # GET_CAN_DUPE
            C.cast(data, C.POINTER(C.c_bool))[0] = True
            return True
        return False

    def video(self, data, w, h, pitch):
        if data:
            self.fbw, self.fbh, self.fbpitch = w, h, pitch
            self.fb = C.string_at(data, pitch * h)

    def now(self):
        return self.frame_no * MCYC_PER_FRAME + self.lib.geo_dbg_mcycs()

    def state(self, port, device, index, idn):
        if device != 1 or port > 1:
            return 0
        if idn in (LEFT, RIGHT) and self.spin_on[port]:
            if idn == LEFT:
                self.reads[port] += 1
            a, b = self.spin[port].phase(self.now())
            return a if idn == LEFT else b
        return 1 if idn in self.held[port] else 0

    # ---- control
    def run(self, n=1):
        for _ in range(n):
            self.lib.retro_run()
            self.frame_no += 1

    def press(self, port, *btns):
        for b in btns:
            self.held[port].add(BTN[b])

    def release(self, port, *btns):
        for b in btns:
            self.held[port].discard(BTN[b])

    def tap(self, port, btn, hold=3, after=3):
        self.press(port, btn); self.run(hold); self.release(port, btn); self.run(after)

    def spinner(self, port, on=True, quantum_us=0, invert=False):
        self.spin_on[port] = on
        self.spin[port].quantum = quantum_us
        self.spin[port].invert = invert

    def spin_rate(self, port, rate):
        self.spin[port].set_rate(self.now(), rate)

    def spin_counts(self, port, counts, rate=600.0):
        """Turn the knob by `counts` quadrature counts at `rate` counts/s, then stop."""
        if counts == 0:
            return
        r = abs(rate) * (1 if counts > 0 else -1)
        start = self.spin[port].count(self.now())
        target = start + counts
        self.spin[port].target = None
        self.spin_rate(port, r)
        self.spin[port].target = target
        while (self.spin[port].count(self.now()) - target) * (1 if counts > 0 else -1) < 0:
            self.run(1)
        # arrived (the position saturates at target); stop there
        self.spin[port].rate = 0
        self.spin[port].pos = target
        self.spin[port].t0 = self.now()
        self.spin[port].target = None

    def r8(self, a):
        return self.ram[a - 0x100000] if 0x100000 <= a < 0x110000 else None

    def r16(self, a):
        return (self.r8(a) << 8) | self.r8(a + 1)

    def peek(self, a, n):
        return bytes(self.r8(a + i) for i in range(n))

    def pc(self):
        return self.lib.m68k_get_reg(None, 16)

    def shot(self, path):
        from PIL import Image
        w, h, p = self.fbw, self.fbh, self.fbpitch
        if self.pixfmt == 1:  # XRGB8888
            img = Image.frombuffer('RGBX', (w, h), self.fb, 'raw', 'BGRX', p, 1).convert('RGB')
        else:  # RGB565
            img = Image.frombuffer('RGB', (w, h), self.fb, 'raw', 'BGR;16', p, 1)
        img.save(path)

    def save_state(self):
        L = self.lib
        L.retro_serialize_size.restype = C.c_size_t
        n = L.retro_serialize_size()
        buf = C.create_string_buffer(n)
        L.retro_serialize.restype = C.c_bool
        assert L.retro_serialize(buf, C.c_size_t(n))
        return (buf.raw, self.frame_no)

    def load_state(self, st):
        raw, fno = st
        buf = C.create_string_buffer(raw, len(raw))
        self.lib.retro_unserialize.restype = C.c_bool
        assert self.lib.retro_unserialize(buf, C.c_size_t(len(raw)))
        self.frame_no = fno


class DbgRec(C.Structure):
    _fields_ = [('pc', C.c_uint32), ('addr', C.c_uint32), ('val', C.c_uint32), ('rwsize', C.c_uint32)]


def watch(n, lo, hi, reads=True, writes=True):
    n.lib.geo_dbg_watch(C.c_uint32(lo), C.c_uint32(hi), C.c_uint32((1 if reads else 0) | (2 if writes else 0)))


def watch_log(n):
    n.lib.geo_dbg_logptr.restype = C.POINTER(DbgRec)
    n.lib.geo_dbg_get_count.restype = C.c_uint32
    cnt = n.lib.geo_dbg_get_count()
    p = n.lib.geo_dbg_logptr()
    return [(p[i].pc, p[i].addr, p[i].val, p[i].rwsize >> 8, p[i].rwsize & 0xff) for i in range(cnt)]


def w8(n, a, v):
    n.ram[a - 0x100000] = v & 0xff


def snd_log(n):
    n.lib.geo_dbg_sndptr.restype = C.POINTER(C.c_uint32)
    n.lib.geo_dbg_sndcount.restype = C.c_uint32
    p = n.lib.geo_dbg_sndptr()
    out = [(p[i] >> 8, p[i] & 0xff) for i in range(n.lib.geo_dbg_sndcount())]
    n.lib.geo_dbg_sndclear()
    return out


class VRec(C.Structure):
    _fields_ = [('pc', C.c_uint32), ('addr', C.c_uint16), ('val', C.c_uint16)]


def vlog_on(n, on=True):
    n.lib.geo_dbg_vctl(C.c_uint32(1 if on else 0))


def vlog(n):
    n.lib.geo_dbg_vlogptr.restype = C.POINTER(VRec)
    n.lib.geo_dbg_vcount.restype = C.c_uint32
    p = n.lib.geo_dbg_vlogptr(); c = n.lib.geo_dbg_vcount()
    return [(p[i].pc, p[i].addr, p[i].val) for i in range(c)]


def vram(n):
    n.lib.geo_lspc_vram_ptr.restype = C.c_void_p
    return (C.c_uint16 * (0x11000 // 2)).from_address(n.lib.geo_lspc_vram_ptr())
