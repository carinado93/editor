from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps
import numpy as np, math, glob, os
W,H=1920,1080; FPS=30
LILAC=(201,179,236); LILD=(122,100,158); PLUM=(74,52,110)
def ease(x): x=max(0,min(1,x)); return 1-(1-x)**3
def eio(x): x=max(0,min(1,x)); return x*x*(3-2*x)
def back(x):
    x=max(0,min(1,x)); c=1.7; return 1+(c+1)*(x-1)**3+c*(x-1)**2
F=lambda n,s: ImageFont.truetype(n,s)
emo=ImageFont.truetype('/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf',109)
def emoji(ch,size):
    im=Image.new('RGBA',(160,160),(0,0,0,0)); ImageDraw.Draw(im).text((10,10),ch,font=emo,embedded_color=True)
    im=im.crop(im.getbbox()); return im.resize((size,int(size*im.height/im.width)),Image.LANCZOS)
def shadowed(T,blur=6,op=0.5,off=(4,6)):
    sh=Image.new('RGBA',T.size,(40,25,70,0)); sh.putalpha(T.split()[3].point(lambda v:int(v*op))); sh=sh.filter(ImageFilter.GaussianBlur(blur))
    o=Image.new('RGBA',T.size,(0,0,0,0)); o.alpha_composite(sh,off); return Image.alpha_composite(o,T)
os.makedirs('mdf',exist_ok=True); [os.remove(f) for f in glob.glob('mdf/*')]
k=[0]
def save(im): im.convert('RGB').save(f'mdf/{k[0]:04d}.png'); k[0]+=1
last=Image.open('o2x/0880.png').convert('RGB')
med=sorted(glob.glob('mf/*.png'))
# ---- 1. pause slam, B&W, slide away (1.1 s)
def pause_icon(s,a):
    w=int(260*s); L=Image.new('RGBA',(W,H),(0,0,0,0)); d=ImageDraw.Draw(L)
    cx,cy=W/2,H/2; r=int(170*s)
    d.ellipse((cx-r,cy-r,cx+r,cy+r),fill=LILAC+(int(235*a),))
    bw,bh,g=int(40*s),int(150*s),int(36*s)
    for sx in (-1,1):
        x0=cx+sx*(g/2+bw/2)-bw/2; d.rounded_rectangle((x0,cy-bh/2,x0+bw,cy+bh/2),int(12*s),fill=(255,255,255,int(255*a)))
    return shadowed(L,14,0.45,(8,14))
for i in range(33):
    t=i/FPS
    fr=last.copy()
    if t>=0.3: q=min(1,(t-0.3)/0.3); fr=Image.blend(fr,ImageOps.grayscale(fr).convert('RGB'),q)
    fr=fr.convert('RGBA')
    s=back(t/0.3)*(1.6-0.6*min(1,t/0.3)) if t<0.3 else 1.0
    a=1 if t<0.75 else max(0,1-(t-0.75)/0.2)
    img=Image.alpha_composite(fr,Image.new('RGBA',(W,H),(0,0,0,int(60*min(1,t/0.2)))))
    img=Image.alpha_composite(img,pause_icon(max(0.05,s),a))
    if t>=0.7:
        p=eio((t-0.7)/0.4); m=Image.open(med[0]).convert('RGBA')
        out=m.copy(); x=int(-W*p); out.alpha_composite(img,(x,0))
        sh=Image.new('RGBA',(W,H),(0,0,0,0)); ImageDraw.Draw(sh).rectangle((x+W,0,x+W+40,H),fill=(0,0,0,90)); out=Image.alpha_composite(out,sh.filter(ImageFilter.GaussianBlur(20)))
        img=out
    save(img)
# ---- 2. meditation: write-on title + 30:00 countdown ring
title=F('/home/claude/w/corm600i.ttf',110); tfont=F('inter800.ttf',96); small=F('fredoka600.ttf',40)
T_TIT=0.3; T_C0=1.0; T_C1=3.9
CX,CY,R=1590,600,165
n=len(med)
for i,f in enumerate(med):
    t=i/FPS; img=Image.open(f).convert('RGBA')
    L=Image.new('RGBA',(W,H),(0,0,0,0))
    v=min(1,max(0,(t-T_TIT)/1.0))
    if v>0:
        T=Image.new('RGBA',(W,H),(0,0,0,0)); ImageDraw.Draw(T).text((1180,120),"meditation time",font=title,fill=PLUM+(255,))
        m=Image.new('L',(W,H),0); ImageDraw.Draw(m).rectangle((0,0,1180+int(720*v),H),fill=255)
        T.putalpha(Image.fromarray(np.minimum(np.array(T.split()[3]),np.array(m)))); L=Image.alpha_composite(L,T)
    u=(t-T_C0+0.3)/0.35
    if u>0:
        s=back(u); a=min(1,u*3)
        p=eio((t-T_C0)/(T_C1-T_C0))
        secs=int(round(1800*(1-p))); txt=f"{secs//60:02d}:{secs%60:02d}"
        C=Image.new('RGBA',(W,H),(0,0,0,0)); d=ImageDraw.Draw(C); r=R*s
        d.ellipse((CX-r,CY-r,CX+r,CY+r),fill=(255,255,255,int(170*a)))
        d.arc((CX-r+10,CY-r+10,CX+r-10,CY+r-10),0,360,fill=LILAC+(int(120*a),),width=14)
        if p>0: d.arc((CX-r+10,CY-r+10,CX+r-10,CY+r-10),-90,-90+360*p,fill=LILD+(int(255*a),),width=14)
        f2=F('inter800.ttf',max(10,int(84*s))); tw=d.textlength(txt,font=f2); d.text((CX-tw/2,CY-50*s),txt,font=f2,fill=PLUM+(int(255*a),))
        lab="mins"; f3=F('fredoka600.ttf',max(8,int(34*s))); lw=d.textlength(lab,font=f3); d.text((CX-lw/2,CY+48*s),lab,font=f3,fill=LILD+(int(255*a),))
        L=Image.alpha_composite(L,shadowed(C,12,0.25,(4,8)))
    # ding pulse at the end
    if t>=T_C1:
        q=(t-T_C1)/0.45
        if q<1:
            P=Image.new('RGBA',(W,H),(0,0,0,0)); rr=int(R+260*ease(q))
            ImageDraw.Draw(P).ellipse((CX-rr,CY-rr,CX+rr,CY+rr),outline=LILAC+(int(255*(1-q)),),width=10); L=Image.alpha_composite(L,P)
    img=Image.alpha_composite(img,L); save(img)
print('med end',k[0])
# ---- 3. back to editing (normal speed) + freeze with second line
ed=sorted(glob.glob('ef2/*.png'))
tf=F('titan.ttf',96)
def pop(L,txt,font,cx,cy,u,col):
    if u<=0: return
    s=back(u); a=min(1,u*3); d=ImageDraw.Draw(Image.new('RGBA',(5,5))); b=d.textbbox((0,0),txt,font=font)
    T=Image.new('RGBA',(b[2]-b[0]+40,b[3]-b[1]+40),(0,0,0,0)); ImageDraw.Draw(T).text((20-b[0],20-b[1]),txt,font=font,fill=col+(255,))
    T=T.resize((max(2,int(T.width*s)),max(2,int(T.height*s))),Image.LANCZOS); T.putalpha(T.split()[3].point(lambda v:int(v*a)))
    L.alpha_composite(T,(int(cx-T.width/2),int(cy-T.height/2)))
BOOM=emoji('🤯',100)
NE=len(ed); FREEZE=int(2.0*FPS)
for i in range(NE+FREEZE):
    t=i/FPS; img=Image.open(ed[min(i,NE-1)]).convert('RGBA')
    if i<3:  # little white flash after the ding
        img=Image.blend(img,Image.new('RGBA',(W,H),(255,255,255,255)),0.5*(1-i/3))
    L=Image.new('RGBA',(W,H),(0,0,0,0))
    if t<NE/FPS:
        pop(L,"ok… NOW back to editing",tf,960,120,(t-0.1)/0.3,LILAC)
    else:
        tt=t-NE/FPS
        pop(L,"editing the app",tf,900,110,(tt)/0.3,LILAC)
        pop(L,"that edits my videos",tf,960,225,(tt-0.2)/0.3,LILAC)
        u=(tt-0.5)/0.3
        if u>0:
            s=back(u); b=BOOM.resize((max(2,int(100*s)),max(2,int(BOOM.height*s))),Image.LANCZOS)
            L.alpha_composite(b,(int(1395-b.width/2),int(110-b.height/2)))
    img=Image.alpha_composite(img,shadowed(L,6,0.8)); save(img)
print('total',k[0])
