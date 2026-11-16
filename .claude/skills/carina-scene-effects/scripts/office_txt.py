# overlays on office clip frames (by clip time)
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import numpy as np, math, random
W,H=1920,1080
PLUMD=(74,52,110); PAPER=(122,100,158); PTXT=(236,224,250)
def ease(x): x=max(0,min(1,x)); return 1-(1-x)**3
def back(x):
    x=max(0,min(1,x)); c=1.7; return 1+(c+1)*(x-1)**3+c*(x-1)**2
thin=ImageFont.truetype('inter300.ttf',72); bold=ImageFont.truetype('anton.ttf',94)
def torn_label(word,seed):
    random.seed(seed)
    d=ImageDraw.Draw(Image.new('RGB',(5,5))); tw=d.textlength(word,font=bold); bb=d.textbbox((0,0),word,font=bold)
    w=int(tw+70); h=int(bb[3]-bb[1]+50)
    im=Image.new('RGBA',(w+20,h+20),(0,0,0,0)); dd=ImageDraw.Draw(im)
    pts=[]
    for x in range(0,w+1,8): pts.append((10+x,10+random.uniform(0,9)))
    for y in range(0,h+1,7): pts.append((10+w-random.uniform(0,8),10+y))
    for x in range(w,-1,-8): pts.append((10+x,10+h-random.uniform(0,9)))
    for y in range(h,-1,-7): pts.append((10+random.uniform(0,8),10+y))
    dd.polygon(pts,fill=PAPER+(255,))
    a=np.array(im).astype(np.float32); n=np.random.RandomState(seed).normal(0,9,a.shape[:2])
    a[...,:3]+=n[...,None]*(a[...,3:]>0); im=Image.fromarray(np.clip(a,0,255).astype(np.uint8))
    dd=ImageDraw.Draw(im); dd.text((10+35-bb[0],10+25-bb[1]),word,font=bold,fill=PTXT+(255,))
    return im
LAB={'dressed':torn_label('DRESSED',3),'home':torn_label('HOME',7)}
def ring(t,t0):
    # ring-ring: shake 0.45s, pause 0.35s
    u=(t-t0)%0.8
    if u>0.45: return 0
    return 7*math.sin(u*2*math.pi*14)*math.sin(u/0.45*math.pi)
def glowtext(img,items):
    T=Image.new('RGBA',(W,H),(0,0,0,0)); d=ImageDraw.Draw(T)
    for txt,x,y,f,col in items: d.text((x,y),txt,font=f,fill=col)
    sh=Image.new('RGBA',(W,H),(0,0,0,0)); sh.putalpha(T.split()[3].point(lambda v:int(v*0.25))); sh=sh.filter(ImageFilter.GaussianBlur(5))
    return Image.alpha_composite(Image.alpha_composite(img,sh),T)
def dressed_overlay(img,ct):
    T0=2.0; T1=8.4
    if ct<T0 or ct>T1+0.3: return img
    fa=1 if ct<T1 else max(0,1-(ct-T1)/0.3)
    img=img.convert('RGBA')
    steps=[('getting',0.0),('dressed',0.35),('for working from…',0.9),('home',1.5)]
    x0=55; y=40; items=[]
    L=Image.new('RGBA',(W,H),(0,0,0,0))
    for txt,dt in steps:
        u=(ct-T0-dt)/0.35
        if txt in LAB:
            lb=LAB[txt]
            if u>0:
                s=back(u); ang=ring(ct,T0+dt+0.4) if u>1 else 0
                im=lb.resize((max(2,int(lb.width*s)),max(2,int(lb.height*s))),Image.LANCZOS).rotate(ang-3 if txt=='dressed' else ang+2,expand=True,resample=Image.BICUBIC)
                im.putalpha(im.split()[3].point(lambda v:int(v*fa)))
                cx=x0+60+lb.width/2 if txt=='dressed' else x0+180+lb.width/2
                L.alpha_composite(im,(int(cx-im.width/2),int(y+lb.height/2-im.height/2)))
            y+=lb.height-6
        else:
            if u>0: items.append((txt,x0,y+(1-ease(u))*20,thin,PLUMD+(int(255*min(1,u*2)*fa),)))
            y+=86
    img=glowtext(img,items); img=Image.alpha_composite(img,L)
    return img.convert('RGB')
f_q=ImageFont.truetype('fredoka600.ttf',86)
def plan_overlay(img,ct):
    T0=8.8; CL=11.15
    if ct<T0 or ct>CL+0.3: return img
    img=img.convert('RGBA')
    lines=["what do we have planned","for today?"]
    T=Image.new('RGBA',(W,H),(0,0,0,0)); d=ImageDraw.Draw(T)
    pop=0 if ct<CL else (ct-CL)/0.3
    sc=1+0.4*pop; al=1-pop
    for j,l in enumerate(lines):
        u=(ct-T0-j*0.4)/0.35
        if u<=0: continue
        f=ImageFont.truetype('fredoka600.ttf',int(86*sc*(0.85+0.15*back(u))))
        tw=d.textlength(l,font=f); y=95+j*105*sc
        d.text((960-tw/2,y),l,font=f,fill=(255,255,255,int(255*al*min(1,u*2))))
    gl=Image.new('RGBA',(W,H),(201,179,236,0)); gl.putalpha(T.filter(ImageFilter.GaussianBlur(16)).split()[3].point(lambda v:min(255,int(v*1.6))))
    sh=Image.new('RGBA',(W,H),(0,0,0,0)); sh.putalpha(T.split()[3].point(lambda v:int(v*0.5))); sh=sh.filter(ImageFilter.GaussianBlur(6))
    img=Image.alpha_composite(img,Image.alpha_composite(Image.alpha_composite(gl,sh),T))
    return img.convert('RGB')
