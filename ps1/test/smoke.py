import sys, os
from env import ROOT
from retro import *
cue = os.path.join(ROOT, 'build', 'PS1 Controller Test.cue')
ports = tuple(sys.argv[1].split(',')) if len(sys.argv) > 1 else ('standard', 'standard')
e = Emu(cue, ports=ports)
e.run(240)
e.shot(os.path.join(ROOT, 'shots', 'boot_%s.png' % '_'.join(ports)))
print(e.frame.shape if e.frame is not None else None)
