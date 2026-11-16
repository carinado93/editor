import numpy as np, cv2, os, math, sys
sys.path.insert(0,'.')
from maskfix import mask_fixed
from PIL import Image, ImageDraw, ImageFont, ImageFilter
W,H=1920,1080; F='/home/claude/w/'
LILAC=(201,179,236); LILD=(122,100,158); WHITE=(255,255,255)
N=506
SH={'Z':(31,'ZUMBA','30 min'),'P':(263,'PILATES','45 min'),'Y':(376,'STRETCHING / YOGA','45 min')}
EMPTY=6; DESC=27   # frames
def fnt(n,s): return ImageFont.truetype(F+n,s)
def eo(x): x=min(max(x,0),1); return 1-(1-x)**3
def eob(x):  # ease out back
    x=min(max(x,0),1); c=1.7; return 1+(c+1)*(x-1)**3+c*(x-1)**2
plates={k:np.array(Image.open(f'plate2_{k}.png').convert('RGB')).astype(np.float32) for k in SH}
def mask(i):
    m=np.array(Image.open(f'mk/{i:04d}.png').convert('L')).astype(np.float32)/255
    m=cv2.resize(m,(W,H),interpolation=cv2.INTER_LINEAR)
    return np.clip((m-0.25)/0.5,0,1)
def frame(i): return np.array(Image.open(f'fr/{i:04d}.png').convert('RGB')).astype(np.float32)

def descend(i,k):
    a=SH[k][0]; j=i-a; pl=plates[k]
    if j<EMPTY: return pl.copy()
    fr=frame(i); m=mask_fixed(i,fr,k=='Z')
    t=(j-EMPTY+1)/DESC; e=eo(t)
    ys,xs=np.nonzero(m>0.5); bot=ys.max(); cx=xs[ys>bot-60].mean()
    dy=-(bot+40)*(1-e); s=1+0.10*(1-e)
    M=np.float32([[s,0,cx-s*cx],[0,s,bot-s*bot+dy]])
    cut=cv2.warpAffine(fr,M,(W,H),borderMode=cv2.BORDER_REPLICATE)
    mm=cv2.warpAffine(m,M,(W,H))
    v=(bot+40)*3*(1-t)**2/DESC  # px per frame
    if v>6:
        k_=int(min(v,32))|1; ker=np.zeros((k_,1),np.float32); ker[:]=1/k_
        cut=cv2.filter2D(cut,-1,ker); mm=cv2.filter2D(mm,-1,ker)
    out=pl.copy()
    # shadow
    sh=np.zeros((H,W),np.float32)
    sw=int(260*(0.4+0.6*e)); cv2.ellipse(sh,(int(cx),int(bot)),(sw,int(sw*0.16)),0,0,360,1,-1)
    sh=cv2.GaussianBlur(sh,(0,0),25)*0.45*e
    out*= (1-sh)[...,None]
    out=out*(1-mm[...,None])+cut*mm[...,None]
    # land: blend to original over last 4 frames
    rem=EMPTY+DESC-1-j
    if rem<4: w=1-rem/4; out=out*(1-w)+fr*w
    return out

def ripple(img,i,k):
    a=SH[k][0]; j=i-(a+EMPTY+DESC-3)
    if not 0<=j<14: return
    q=a+EMPTY+DESC-3; m=mask_fixed(q,frame(q),k=='Z'); ys,xs=np.nonzero(m>0.5); bot=ys.max(); cx=xs[ys>bot-60].mean()
    lay=Image.new('RGBA',(W,H),(0,0,0,0)); d=ImageDraw.Draw(lay)
    t=j/14; r=200+380*eo(t); al=int(200*(1-t))
    for rr,w in ((r,10),(r*0.7,6)):
        d.ellipse([cx-rr,bot-rr*0.17,cx+rr,bot+rr*0.17],outline=LILAC+(al,),width=w)
    img.alpha_composite(lay.filter(ImageFilter.GaussianBlur(1.5)))

def stopwatch(d,cx,cy,r,ang,col):
    d.ellipse([cx-r,cy-r,cx+r,cy+r],outline=col,width=max(3,r//5))
    d.rectangle([cx-r*0.25,cy-r*1.45,cx+r*0.25,cy-r*1.15],fill=col)
    d.line([cx,cy,cx+r*0.7*math.sin(ang),cy-r*0.7*math.cos(ang)],fill=col,width=max(3,r//6))

def pill(img,k,i):
    a,name,mins=SH[k]; land=max(a+2,52) if k=="Z" else a+2
    keys=list(SH); nxt=keys.index(k)+1
    end=SH[keys[nxt]][0]+2 if nxt<len(keys) else 10**9
    if i<land or i>=end+8: return
    j=i-land
    sc=eob(j/9)
    out=0 if i<end else eo((i-end)/8)
    f1=fnt('titan.ttf',64); f2=fnt('fredoka700.ttf',52)
    tw=f1.getlength(name); mw=f2.getlength('× '+mins)
    pw=int(110+tw+30+mw+50); ph=110
    p=Image.new('RGBA',(pw+20,ph+20),(0,0,0,0)); d=ImageDraw.Draw(p)
    d.rounded_rectangle([10,14,pw+10,ph+14],ph//2,fill=(90,70,125,90))
    d.rounded_rectangle([10,10,pw+10,ph+10],ph//2,fill=LILAC+(255,))
    stopwatch(d,10+62,10+ph//2+6,26,j*0.35,WHITE)
    d.text((10+110,10+ph//2),name,font=f1,fill=WHITE,anchor='lm')
    d.rounded_rectangle([10+110+tw+20,10+20,10+110+tw+20+mw+30,ph-10],30,fill=WHITE)
    d.text((10+110+tw+35,10+ph//2+2),'× '+mins,font=f2,fill=LILD,anchor='lm')
    s=max(sc,0.01)*(1-0.3*out)
    p=p.resize((max(1,int(p.width*s)),max(1,int(p.height*s))),Image.LANCZOS)
    if out>0: p.putalpha(p.getchannel('A').point(lambda v:int(v*(1-out))))
    x=80; y=int(70-120*out)
    img.alpha_composite(p,(x,y))

def title(img,i):
    if i>52: return
    l1='and now…'; l2='SPORTS AT HOME'
    f1=fnt('fredoka600.ttf',78); f2=fnt('titan.ttf',150)
    lay=Image.new('RGBA',(W,H),(0,0,0,0)); d=ImageDraw.Draw(lay)
    out=eo((i-42)/10) if i>42 else 0
    a1=eo((i-2)/8)
    d.text((W/2,400-30*(1-a1)),l1,font=f1,fill=WHITE+(int(255*a1*(1-out)),),anchor='mm')
    tw=f2.getlength(l2); x=W/2-tw/2
    for n,ch in enumerate(l2):
        t=(i-8-n*1.0)/7; e=eob(t) if t>0 else 0
        if e<=0: x+=f2.getlength(ch); continue
        al=int(255*min(1,t*3)*(1-out))
        y=540-90*(1-e)-80*out
        d.text((x+5,y+7),ch,font=f2,fill=LILD+(al,),anchor='lm')
        d.text((x,y),ch,font=f2,fill=WHITE+(al,),anchor='lm')
        x+=f2.getlength(ch)
    img.alpha_composite(lay)

def main(lo,hi):
  for i in range(lo,hi):
      k=None
      for kk,(a,_,_) in SH.items():
          if a<=i<a+EMPTY+DESC: k=kk
      base=descend(i,k) if k else frame(i)
      img=Image.fromarray(np.clip(base,0,255).astype(np.uint8)).convert('RGBA')
      for kk in SH: ripple(img,i,kk); pill(img,kk,i)
      title(img,i)
      img.convert('RGB').save(f'out/{i:04d}.png')

if __name__=='__main__': main(int(sys.argv[1]),int(sys.argv[2]))
