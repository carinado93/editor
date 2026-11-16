from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops
import numpy as np, math, os, glob
W,H=1920,1080; T0=2.1; FPS=30
LILAC=(201,179,236)
f=ImageFont.truetype('titan.ttf',150)
def ease(x): x=max(0,min(1,x)); return 1-(1-x)**3
def draw_wand(base,tip):
    S=2; L=Image.new('RGBA',(W*S,H*S),(0,0,0,0)); d=ImageDraw.Draw(L)
    bx,by=base; tx,ty=tip; dx,dy=tx-bx,ty-by; ln=math.hypot(dx,dy); ux,uy=dx/ln,dy/ln; nx,ny=-uy,ux
    def pt(t,w,side): return ((bx+dx*t+nx*w*side)*S,(by+dy*t+ny*w*side)*S)
    # shaft: taper 15 -> 4 px half width
    N=40; left=[];right=[]
    for i in range(N+1):
        t=i/N; w=22-15*t if t>0.25 else 27
        left.append(pt(t,w,1)); right.append(pt(t,w,-1))
    d.polygon(left+right[::-1],fill=(44,28,20,255))
    # highlight line
    d.line([pt(t,9-6*t if t>0.25 else 13,1) for t in np.linspace(0.02,0.97,30)],fill=(120,86,62,255),width=3*S)
    # handle rings
    for t in [0.06,0.14,0.22,0.26]:
        d.line([pt(t,29,1),pt(t,29,-1)],fill=(25,15,10,255),width=5*S)
    L=L.resize((W,H),Image.LANCZOS)
    sh=Image.new('RGBA',(W,H),(0,0,0,0)); sh.paste((0,0,0,140),(0,0),L.split()[3].point(lambda a:a))
    sh=ImageChops.offset(sh,8,10).filter(ImageFilter.GaussianBlur(8))
    return Image.alpha_composite(sh,L)
def add_light(img,c,r,amt):
    a=np.asarray(img).astype(np.float32)
    yy,xx=np.mgrid[0:H,0:W]; dd=np.hypot(xx-c[0],yy-c[1])
    core=np.exp(-(dd/(r*0.12))**2)*1.0
    halo=np.exp(-(dd/(r*0.45))**2)*0.55
    room=np.exp(-(dd/(r*2.2))**2)*0.35
    col=np.array([235,240,255],np.float32)
    a[...,:3]=a[...,:3]*(1+room[...,None]*amt*1.2)+col*(core+halo)[...,None]*amt
    return Image.fromarray(np.clip(a,0,255).astype(np.uint8))
def lumos_layer(tip,p):
    L=Image.new('RGBA',(W,H),(0,0,0,0)); d=ImageDraw.Draw(L)
    s=0.35+0.65*ease(p); fs=ImageFont.truetype('cinzel.ttf',int(100*s))
    b=d.textbbox((0,0),'Lumos',font=fs); w,h=b[2]-b[0],b[3]-b[1]
    cx=tip[0]-60+90*ease(p); cy=tip[1]-80-200*ease(p)
    x,y=cx-w/2-b[0],cy-h/2-b[1]
    g=Image.new('RGBA',(W,H),(0,0,0,0)); ImageDraw.Draw(g).text((x,y),'Lumos',font=fs,fill=(255,255,255,230))
    g=g.filter(ImageFilter.GaussianBlur(14))
    d.text((x,y),'Lumos',font=fs,fill=LILAC+(255,))
    a=min(1,p*4); out=Image.alpha_composite(g,L)
    out.putalpha(out.split()[3].point(lambda v:int(v*a))); return out
BASE=(-40,980); TIP_FINAL=(470,540)
