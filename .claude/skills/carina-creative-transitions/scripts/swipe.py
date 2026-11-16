from PIL import Image
import numpy as np, os, glob
W,H=1920,1080
def eio(x): x=max(0,min(1,x)); return x*x*(3-2*x)
os.makedirs('swf',exist_ok=True); [os.remove(f) for f in glob.glob('swf/*')]
n=8
xx=np.arange(W)[None,:,None].astype(np.float32)
def hblur(a,amt):
    if amt<1: return a
    acc=a.copy(); k=6
    for i in range(1,k):
        d=int(amt*i/k); acc+=np.concatenate([np.repeat(a[:,:1],d,axis=1),a[:,:-d]],axis=1)
    return acc/k
for i in range(n):
    p=eio((i+0.5)/n)
    old=np.asarray(Image.open(f'sk/{678+i:04d}.png').convert('RGB')).astype(np.float32)
    new=np.asarray(Image.open(f'n6/{i+1:04d}.png').convert('RGB')).astype(np.float32)
    bl=60*np.sin(np.pi*(i+0.5)/n)
    old=hblur(old,bl); new=hblur(new,bl)
    b=-150+(W+300)*p
    m=np.clip((b-xx)/90+0.5,0,1)   # left of boundary = new
    out=new*m+old*(1-m)
    Image.fromarray(np.clip(out,0,255).astype(np.uint8)).save(f'swf/{i:03d}.png')
print('ok')
