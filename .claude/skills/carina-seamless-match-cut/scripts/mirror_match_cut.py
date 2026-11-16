from PIL import Image
import numpy as np, cv2, glob, os
from scipy import ndimage as nd
K=1.4  # 2688/1920
def ease(x): x=max(0,min(1,x)); return x*x*(3-2*x)
def comp(path,cond):
    m=np.array(Image.open(path))>128; lab,n=nd.label(m); out=np.zeros_like(m)
    for i in range(1,n+1):
        ys,xs=np.where(lab==i)
        if len(xs)>2500 and cond(xs): out|=lab==i
    return out
def hblur(a,d=36):
    acc=a.astype(np.float32).copy(); n=1
    for s in range(6,d,6): acc+=np.concatenate([np.repeat(a[:,:1],s,1),a[:,:-s]],1); n+=1
    return acc/n
BSRC=[f'sb4/{i:03d}' for i in range(1,9)]
SW=1.0
def crop_zoom(img,Z,cx,cy):  # img full-res 2688; cx,cy,Z in 1920 coords
    hw,hh=960/Z*K,540/Z*K; X=cx*K; Y=cy*K
    x0,y0=int(round(X-hw)),int(round(Y-hh)); x1,y1=int(round(X+hw)),int(round(Y+hh))
    x0=max(0,x0); y0=max(0,y0); x1=min(img.shape[1],x1); y1=min(img.shape[0],y1)
    return cv2.resize(img[y0:y1,x0:x1],(1920,1080),interpolation=cv2.INTER_AREA)
ZA,CA=1.46,(862,709)
ZB,CB=1.46,(900,370)
os.makedirs('fin',exist_ok=True); [os.remove(f) for f in glob.glob('fin/*')]
k_out=0
# --- A frames 11.8 .. 12.133 (ar 1..11) with reflection swap (ar4..11) and zoom ramp
NA=17
for k in range(1,NA+1):
    A=np.array(Image.open(f'ar/{k:03d}.png').convert('RGB'))
    if k>=10:
        j=k-9
        ma=comp(f'sa2/m{j:03d}.png',lambda xs: xs.mean()<1300 and xs.min()<1250)
        real=comp(f'sa2/m{j:03d}.png',lambda xs: xs.max()>=1900 and xs.mean()>1300)
        ma&=~real
        ys,xs=np.where(ma); right=xs.max(); top=max(ys.min(),560)
        mab=cv2.resize(nd.binary_dilation(ma,iterations=34).astype(np.uint8)*255,(A.shape[1],A.shape[0]),interpolation=cv2.INTER_NEAREST)
        Ain=cv2.inpaint(A,mab,15,cv2.INPAINT_TELEA).astype(np.float32)
        Bf=np.array(Image.open(BSRC[j-1]+'.png').convert('RGB'))
        mb=comp(BSRC[j-1].replace('/','/m')+'.png',lambda xs: xs.mean()<1350 and xs.min()<1100)
        bys,bxs=np.where(mb); bx0,bx1,by0,by1=bxs.min(),bxs.max()+1,bys.min(),bys.max()+1
        crop=Bf[by0:by1,bx0:bx1].astype(np.float32); cm=mb[by0:by1,bx0:bx1].astype(np.float32)
        mfull=cv2.resize(ma.astype(np.uint8),(A.shape[1],A.shape[0]))>0
        ref=A[mfull].reshape(-1,3).mean(0); src=Bf[mb].reshape(-1,3).mean(0)
        crop=crop*(ref/src)
        s=SW*K; nw,nh=int(crop.shape[1]*s),int(crop.shape[0]*s)
        crop=cv2.resize(crop,(nw,nh)); cm=cv2.resize(cm,(nw,nh))
        px=int(right*K-nw); py=int(top*K)
        H,W=A.shape[:2]; layer=np.zeros((H,W,3),np.float32); lm=np.zeros((H,W),np.float32)
        X0,Y0=max(0,px),max(0,py); X1,Y1=min(W,px+nw),min(H,py+nh)
        layer[Y0:Y1,X0:X1]=crop[Y0-py:Y1-py,X0-px:X1-px]; lm[Y0:Y1,X0:X1]=cm[Y0-py:Y1-py,X0-px:X1-px]
        blur=int(50*K*max(0.25,1-(j-1)/7))
        layer=hblur(layer*lm[...,None],blur); lmb=hblur(lm[...,None],blur)[...,0]; lmb=cv2.GaussianBlur(lmb,(0,0),2)
        rgb=np.where(lmb[...,None]>1e-3,layer/np.maximum(lmb[...,None],1e-3),0)
        rm=cv2.GaussianBlur(cv2.resize(real.astype(np.float32),(W,H)),(0,0),3)
        a=np.clip(lmb,0,1)*(1-rm)
        A=np.clip(Ain*(1-a[...,None])+rgb*a[...,None],0,255).astype(np.uint8)
    p=ease((k-1)/(NA-1)); Z=1+(ZA-1)*p; cx=960+(CA[0]-960)*p; cy=540+(CA[1]-540)*p
    outA=crop_zoom(A,Z,cx,cy); Image.fromarray(outA).save(f'fin/{k_out:04d}.png'); k_out+=1
    lastA=outA
# --- B frames from 26.667: zoom ZB, ease back to 1 between 29.55-29.95
for i,f in enumerate(sorted(glob.glob('br/*.png'))):
    t=27.567+i/30; Bf=np.array(Image.open(f).convert('RGB'))
    p=ease((t-29.55)/0.4); Z=ZB+(1-ZB)*p; cx=CB[0]+(960-CB[0])*p; cy=CB[1]+(540-CB[1])*p
    off=150*(0.6**(i+1)) if i<12 else 0
    o=crop_zoom(Bf,Z,cx+off,cy).astype(np.float32)
    if i<6:
        bl=int(90*(0.6**i))
        if bl>4:
            acc=o.copy(); n=1
            for d in range(8,bl,8): acc+=np.concatenate([np.repeat(o[:,:1],d,1),o[:,:-d]],1); n+=1
            o=acc/n
    if i==0:
        la=lastA.reshape(-1,3).astype(np.float32); lb=o.reshape(-1,3)
        MA,SA=la.mean(0),la.std(0); MB,SB=lb.mean(0),lb.std(0)
    g=1-ease(i/36)
    if g>0:
        m=(o-MB)/np.maximum(SB,1)*SA+MA; o=o*(1-g)+m*g
    Image.fromarray(np.clip(o,0,255).astype(np.uint8)).save(f'fin/{k_out:04d}.png'); k_out+=1
print(k_out)
