import os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CORE = os.environ.get('PCSX_CORE', '/home/claude/tools/pcsx_rearmed/pcsx_rearmed_libretro.so')
os.makedirs(os.path.join(ROOT, 'sys'), exist_ok=True); os.makedirs(os.path.join(ROOT, 'shots'), exist_ok=True)
