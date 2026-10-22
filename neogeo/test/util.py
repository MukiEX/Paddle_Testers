import neo,pickle
from PIL import Image
def load(st='st_after_start.pkl', rom='in/magdrop3.neo'):
    n=neo.Neo(rom)
    if st: n.load_state(pickle.load(open(st,'rb')))
    return n
class Film:
    def __init__(s): s.frames=[]
    def add(s,n,label=''):
        from PIL import ImageDraw
        im=Image.frombuffer('RGBX',(n.fbw,n.fbh),n.fb,'raw','BGRX',n.fbpitch,1).convert('RGB')
        if label: ImageDraw.Draw(im).text((2,2),label,fill=(255,255,0))
        s.frames.append(im)
    def save(s,path,cols=4,scale=1.0):
        w,h=s.frames[0].size; rows=(len(s.frames)+cols-1)//cols
        W=Image.new('RGB',(w*cols,h*rows))
        for i,im in enumerate(s.frames): W.paste(im,((i%cols)*w,(i//cols)*h))
        if scale!=1.0: W=W.resize((int(W.width*scale),int(W.height*scale)))
        W.save(path)
