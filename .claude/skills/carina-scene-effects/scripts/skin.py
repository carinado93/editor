# Builds frames for: glass wipe (on 11144 end), osmo section, phone section, fullscreen + jump
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import numpy as np, math, os, glob
W,H=1920,1080; FPS=30
LIL=(214,198,240); DOT=(255,255,255); PLUM=(74,52,110); LILD=(122,100,158)
def ease(x): x=max(0,min(1,x)); return 1-(1-x)**3
def eio(x): x=max(0,min(1,x)); return x*x*(3-2*x)
def back(x):
    x=max(0,min(1,x)); c=1.7; return 1+(c+1)*(x-1)**3+c*(x-1)**2
def dots_bg(t):
    im=Image.new('RGB',(W,H),LIL); d=ImageDraw.Draw(im); off=(t*20)%80
    for yy in range(-80,H+80,80):
        for xx in range(-80,W+80,80):
            sx=xx+(40 if (yy//80)%2 else 0)+off; sy=yy+off*0.5
            d.ellipse((sx-7,sy-7,sx+7,sy+7),fill=DOT)
    return im
PLAIN=Image.new('RGB',(W,H),LIL)
SK=lambda ct: f'sk/{max(1,min(697,int(round(ct*FPS))+1)):04d}.png'
OUT='skf'; os.makedirs(OUT,exist_ok=True); [os.remove(f) for f in glob.glob(OUT+'/*')]
k=[0]
def save(img):
    img.convert('RGB').save(f'{OUT}/{k[0]:05d}.png'); k[0]+=1
# ---------- 1+2. pull-back into osmo screen, push back in
osmo=Image.open('osmo_cut.png'); OS=760/osmo.height
osm=osmo.resize((int(osmo.width*OS),int(osmo.height*OS)),Image.LANCZOS)
SCR=(309,558,684,763)
cx0=W/2-(SCR[0]+SCR[2])/2*OS+osm.width/2; top0=H/2-(SCR[1]+SCR[3])/2*OS
sx0=cx0-osm.width/2+SCR[0]*OS; sy0=top0+SCR[1]*OS; sw=(SCR[2]-SCR[0])*OS; sh=(SCR[3]-SCR[1])*OS
SC=(sx0+sw/2, sy0+sh/2); ZMAX=W/sw
def zoom_frame(Z,content,tt):
    scene=PLAIN.copy().convert('RGBA'); scene.alpha_composite(osm,(int(cx0-osm.width/2),int(top0)))
    if Z<1.001:
        img=scene.convert('RGB')
    else:
        z=scene.resize((int(W*Z),int(H*Z)),Image.BILINEAR); ox=SC[0]*Z-W/2; oy=SC[1]*Z-H/2
        img=z.crop((int(ox),int(oy),int(ox)+W,int(oy)+H)).convert('RGB')
    rx0=W/2+(sx0-SC[0])*Z; ry0=H/2+(sy0-SC[1])*Z; rw=sw*Z; rh=sh*Z
    img.paste(content.resize((max(2,int(rw)),max(2,int(rh))),Image.LANCZOS),(int(rx0),int(ry0)))
    return img
def mblur(img,amt):
    if amt<0.01: return img
    a=np.asarray(img).astype(np.float32); acc=a.copy(); n=5
    for i in range(1,n):
        d=int(amt*40*i/n)
        if d>0: acc+=np.concatenate([np.repeat(a[:1],d,axis=0),a[:-d]],axis=0)
        else: acc+=a
    return Image.fromarray((acc/n).astype(np.uint8))
NB=9; NH=4; NP=10
for i in range(NB):   # pull back: glass shot shrinks into the osmo screen
    p=ease(i/(NB-1)); Z=math.exp(math.log(ZMAX)*(1-p))
    save(mblur(zoom_frame(Z,Image.open(f'c4w/{i+1:04d}.png').convert('RGB'),i/FPS),(1-p)*0.6))
for i in range(NH):   # hold: screen flips to skincare clip
    save(zoom_frame(1.0,Image.open(SK(i/FPS)).convert('RGB'),(NB+i)/FPS))
for i in range(NP):   # push in
    p=eio((i+1)/NP)**1.3; Z=math.exp(math.log(ZMAX)*p)
    save(mblur(zoom_frame(Z,Image.open(SK((NH+i)/FPS)).convert('RGB'),(NB+NH+i)/FPS),p*0.5))
T_FULL=(NH+NP)/FPS; T_CLICK=0
CT0=T_FULL-T_CLICK   # clip time at full screen (0.8)
# ---------- 3. full until 1.15, then phone 1.15 -> 16.15, expand to full by 16.6
PH_IN=1.15; PH_IN_END=1.6; PH_OUT=16.15; PH_OUT_END=16.6
SCRN=(80,250,80+1000,250+562); BZ=26
f_h=ImageFont.truetype('fredoka600.ttf',47); f_c=ImageFont.truetype('fredoka600.ttf',37)
HEAD=["while my skincare does its thing,","a few things about me:"]
CARDS=["quit my corporate job to become a stress & burnout prevention coach","learning to edit","learning to survive self-employment","learning to be my own boss","learning that teaching stress prevention and following my own rules are two different things","quit my job because of overworking. now I work 24/7."]
CT=[2.2,4.4,6.6,8.8,11.0,13.3]; HT=1.6
CX0,CX1=1150,1875
def wrap(txt,font,w):
    words=txt.split(); lines=[]; cur=''
    dd=ImageDraw.Draw(Image.new('RGB',(5,5)))
    for wd in words:
        t2=(cur+' '+wd).strip()
        if dd.textlength(t2,font=font)<=w: cur=t2
        else: lines.append(cur); cur=wd
    lines.append(cur); return lines
cards=[]; y=215
for i,txt in enumerate(CARDS):
    fnt=ImageFont.truetype('fredoka600.ttf',39) if i==5 else f_c
    lines=wrap(txt,fnt,CX1-CX0-110); hh=28+len(lines)*47
    im=Image.new('RGBA',(CX1-CX0,hh),(0,0,0,0)); d=ImageDraw.Draw(im)
    if i==5: d.rounded_rectangle((0,0,im.width-1,hh-1),20,fill=LILD+(255,)); tc=(255,255,255); bc=(255,255,255); nc=LILD
    else: d.rounded_rectangle((0,0,im.width-1,hh-1),20,fill=(255,255,255,245),outline=(180,154,216,255),width=3); tc=(60,45,80); bc=(180,154,216); nc=(255,255,255)
    d.ellipse((20,hh/2-24,68,hh/2+24),fill=bc); nm=str(i+1); d.text((44-d.textlength(nm,font=f_c)/2,hh/2-20),nm,font=f_c,fill=nc)
    for j,l in enumerate(lines): d.text((90,13+j*47),l,font=fnt,fill=tc)
    cards.append((im,y)); y+=hh+12
print('cards end y',y)
def phone_frame(rect):
    x0,y0,x1,y1=rect; L=Image.new('RGBA',(W,H),(0,0,0,0)); d=ImageDraw.Draw(L)
    d.rounded_rectangle((x0-BZ,y0-BZ,x1+BZ,y1+BZ),60,fill=(22,20,26,255))
    d.rounded_rectangle((x0-BZ+4,y0-BZ+4,x1+BZ-4,y1+BZ-4),56,outline=(70,66,78,255),width=3)
    d.rounded_rectangle((x0-16,(y0+y1)/2-60,x0-8,(y0+y1)/2+60),4,fill=(0,0,0,255))  # dynamic island (landscape: left)
    return L
def screen_mask(rect,rad=34):
    m=Image.new('L',(W,H),0); ImageDraw.Draw(m).rounded_rectangle(rect,rad,fill=255); return m
yy,xx=np.mgrid[0:540,0:960]
def light_trail(img960,idx,ct):
    mp=f'ltm/{idx:04d}.png'
    if not os.path.exists(mp): return img960
    m=Image.open(mp).convert('L')
    big=m.filter(ImageFilter.MaxFilter(9)); edge=np.array(big).astype(np.float32)-np.array(m.filter(ImageFilter.MinFilter(3))).astype(np.float32)
    edge=np.clip(edge,0,255)/255
    # travelling highlight along y
    ph=(ct*1.6)%1.0; trav=0.55+0.45*np.cos((yy/540-ph)*2*np.pi*2)
    fade=min(1,(ct-3.0)/0.3,(6.0-ct)/0.3)
    glow=Image.fromarray((edge*255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(6))
    g=np.array(glow).astype(np.float32)/255
    a=np.array(img960).astype(np.float32)
    col1=np.array([235,215,255],np.float32); col2=np.array([255,255,255],np.float32)
    a=a+(g*2.6*trav*fade)[...,None]*col1+(edge*trav*fade)[...,None]*col2*1.1
    return Image.fromarray(np.clip(a,0,255).astype(np.uint8))
def cards_layer(img,ct):
    if ct>=HT:
        p=ease((ct-HT)/0.35); d=ImageDraw.Draw(img)
        tl=Image.new('RGBA',(W,H),(0,0,0,0)); dl=ImageDraw.Draw(tl)
        for j,hl in enumerate(HEAD): dl.text((CX0,70+j*56+20*(1-p)),hl,font=f_h,fill=PLUM+(int(255*p),)); img.alpha_composite(tl)
    for i,(im,y) in enumerate(cards):
        if ct<CT[i]: continue
        u=(ct-CT[i])/0.35; s=back(u) if i==5 else 0.9+0.1*back(u); a=min(1,u*2)
        if i==5: s*= 1+0.04*math.sin(max(0,ct-CT[i]-0.35)*4)
        c=im.resize((max(2,int(im.width*s)),max(2,int(im.height*s))),Image.LANCZOS)
        c.putalpha(c.split()[3].point(lambda v:int(v*a)))
        img.alpha_composite(c,(int(CX0+im.width/2-c.width/2+40*(1-ease(u))),int(y+im.height/2-c.height/2)))
    return img
def lerp_rect(a,b,p): return tuple(a[i]+(b[i]-a[i])*p for i in range(4))
FULLR=(0,0,W,H)
ct=CT0
JUMP_UP_END=17.5334  # last pyjama frame time (frame 527)
while ct<JUMP_UP_END-1e-6:
    idx=int(round(ct*FPS))+1
    fr=Image.open(f'sk/{idx:04d}.png').convert('RGB')
    if ct<PH_IN or ct>=PH_OUT_END:
        save(fr)
    else:
        if ct<PH_IN_END: p=eio((ct-PH_IN)/(PH_IN_END-PH_IN)); rect=lerp_rect(FULLR,SCRN,p); bga=p
        elif ct>=PH_OUT: p=eio((ct-PH_OUT)/(PH_OUT_END-PH_OUT)); rect=lerp_rect(SCRN,FULLR,p); bga=1-p
        else: rect=SCRN; bga=1
        img=PLAIN.copy().convert('RGBA')
        img=cards_layer(img,ct)
        rw=int(rect[2]-rect[0]); rh=int(rect[3]-rect[1])
        src=fr
        c=src.resize((rw,rh),Image.LANCZOS)
        rad=int(34*min(1,bga*1.5))
        if bga>0.02:
            pf=phone_frame(rect)
            pf.putalpha(pf.split()[3].point(lambda v:int(v*min(1,bga*1.5))))
            sh=Image.new('RGBA',(W,H),(0,0,0,0)); ImageDraw.Draw(sh).rounded_rectangle((rect[0]-BZ+10,rect[1]-BZ+24,rect[2]+BZ+10,rect[3]+BZ+24),60,fill=(40,20,70,int(90*bga)))
            img=Image.alpha_composite(img,sh.filter(ImageFilter.GaussianBlur(24))); img=Image.alpha_composite(img,pf)
        lay=Image.new('RGBA',(W,H),(0,0,0,0)); lay.paste(c,(int(rect[0]),int(rect[1])))
        img=Image.composite(lay,img,screen_mask(rect,rad)) if rad>0 else Image.alpha_composite(img,lay)
        save(img)
    ct+=1/FPS
print('pyjama end frame',k[0])
# ---------- 4. robe after jump: from frame 574 to end
for idx in range(574,698):
    save(Image.open(f'sk/{idx:04d}.png'))
print('total',k[0])
