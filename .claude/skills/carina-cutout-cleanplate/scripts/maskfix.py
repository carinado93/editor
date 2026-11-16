import numpy as np, cv2
from PIL import Image
from scipy import ndimage as nd
W,H=1920,1080
def mask_fixed(i,fr,socks=True):
    m=np.array(Image.open(f'mk/{i:04d}.png').convert('L')).astype(np.float32)/255
    m=cv2.resize(m,(W,H)); 
    lab,n=nd.label(m>0.5)
    if n>1:
        sz=nd.sum(np.ones_like(m),lab,range(1,n+1)); keep=lab==(1+int(np.argmax(sz)))
        keep=nd.binary_dilation(keep,iterations=25); m=m*keep
    m=np.clip((m-0.25)/0.5,0,1)
    ys,xs=np.nonzero(m>0.5); bot=ys.max(); cx=xs[ys>bot-60].mean()
    if not socks: return m
    x0,x1=int(max(cx-110,0)),int(min(cx+110,W)); y0,y1=max(bot-30,0),min(bot+110,H)
    g=fr[y0:y1,x0:x1,1]; b=fr[y0:y1,x0:x1,2]
    r_=fr[y0:y1,x0:x1,0]; sock=((b>80)&(r_>165)).astype(np.uint8)
    lab,n=nd.label(sock)
    if n:
        # keep components touching mask
        mb=m[y0:y1,x0:x1]>0.3; mb=nd.binary_dilation(mb,iterations=8)
        ok=[l for l in range(1,n+1) if (mb&(lab==l)).any()]
        sock=np.isin(lab,ok).astype(np.float32)
        sock=cv2.GaussianBlur(cv2.dilate(sock,np.ones((5,5))),(0,0),1.5)
        m[y0:y1,x0:x1]=np.maximum(m[y0:y1,x0:x1],sock)
    return m
