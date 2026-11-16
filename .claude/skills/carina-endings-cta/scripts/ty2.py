import glob, math, numpy as np, os
from PIL import Image, ImageDraw, ImageFont, ImageFilter
W,H=1920,1080; FPS=30; LILAC=(201,179,236); LILD=(122,100,158); PLUM=(74,52,110); WHITE=(255,255,255)
def ease(x): x=max(0,min(1,x)); return 1-(1-x)**3
def ein(x): x=max(0,min(1,x)); return x**3
def back(x): x=max(0,min(1,x)); c=1.7; return max(0.01,1+(c+1)*(x-1)**3+c*(x-1)**2)
F=lambda n,s: ImageFont.truetype('/home/claude/w/'+n,s)
def heart_pts(cx,cy,size,rot=0):
    t=np.linspace(0,2*np.pi,240); x=16*np.sin(t)**3; y=-(13*np.cos(t)-5*np.cos(2*t)-2*np.cos(3*t)-np.cos(4*t))
    c,s=math.cos(rot),math.sin(rot); k=size/34
    return [(cx+(xx*c-yy*s)*k, cy+(xx*s+yy*c)*k+size*0.05) for xx,yy in zip(x,y)]
def heart_mask(cx,cy,size,rot=0,blur=0):
    m=Image.new('L',(W,H),0); ImageDraw.Draw(m).polygon(heart_pts(cx,cy,size,rot),fill=255)
    return m.filter(ImageFilter.GaussianBlur(blur)) if blur else m
emo=ImageFont.truetype('/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf',109)
def emoji(ch,size):
    im=Image.new('RGBA',(160,160),(0,0,0,0)); ImageDraw.Draw(im).text((10,10),ch,font=emo,embedded_color=True)
    im=im.crop(im.getbbox()); return im.resize((size,size),Image.LANCZOS)
MONKEY=emoji('🙈',64); HEARTE=emoji('💜',90)
LIL=Image.new('RGB',(W,H)); g=ImageDraw.Draw(LIL)
for yy in range(H): g.line([(0,yy),(W,yy)],fill=(int(222-16*yy/H),int(208-18*yy/H),int(246-8*yy/H)))
src=sorted(glob.glob('/home/claude/w/ty/src/*.png'))
def frame(i): return Image.open(src[min(i,len(src)-1)]).convert('RGB')
def pmask(i):
    p=f'/home/claude/w/ty/mk/{min(i,156):04d}.png'
    return Image.open(p).convert('L').resize((W,H)).filter(ImageFilter.GaussianBlur(1.2))
tf=F('titan.ttf',160)
LET=[]; d0=ImageDraw.Draw(Image.new('RGB',(5,5)))
xl=640-d0.textlength('THANK',font=tf); x=xl
for ci,ch in enumerate('THANK'): LET.append((ch,x,ci)); x+=d0.textlength(ch,font=tf)
x=1165
for ci,ch in enumerate('YOU'): LET.append((ch,x,ci+5)); x+=d0.textlength(ch,font=tf)
def letters(i,T0):
    L=Image.new('RGBA',(W,H),(0,0,0,0)); d=ImageDraw.Draw(L)
    for ch,x,n in LET:
        u=(i-T0-n*1.2)/6
        if u<=0: continue
        y=300-120*(1-back(u)); a=int(255*min(1,u*2))
        d.text((x+6,y+8),ch,font=tf,fill=PLUM+(int(a*0.55),),anchor='lm'); d.text((x,y),ch,font=tf,fill=LILAC+(a,),anchor='lm')
    return L
out='/home/claude/w/ty/out2'; os.makedirs(out,exist_ok=True); [os.remove(f) for f in glob.glob(out+'/*')]
k=0
def save(im):
    global k; im.convert('RGB').save(f'{out}/{k:04d}.png'); k+=1
T0=128; KISS=147; GROW=15; END_FZ=156
for i in range(0,KISS):
    img=frame(i)
    if i>=T0:
        bg=img.convert('RGBA'); bg.alpha_composite(letters(i,T0)); bg=bg.convert('RGB'); bg.paste(img,(0,0),pmask(i)); img=bg
    save(img)
# heart grows from mouth to cover the frame
MOUTH=(870,330)
for j in range(GROW):
    i=KISS+j; img=frame(i).convert('RGBA'); L=letters(i,T0); img.alpha_composite(L); base=img.convert('RGB'); base.paste(frame(i),(0,0),pmask(i))
    p=ein((j+1)/GROW); size=30+3600*p; cx=MOUTH[0]+(960-MOUTH[0])*p; cy=MOUTH[1]+(540-MOUTH[1])*p
    m=heart_mask(cx,cy,size,rot=0.25*(1-p),blur=6)
    glow=heart_mask(cx,cy,size*1.08,rot=0.25*(1-p),blur=18)
    base.paste(Image.new('RGB',(W,H),WHITE),(0,0),glow.point(lambda v:int(v*0.8)))
    base.paste(LIL,(0,0),m); save(base)
# heart window reveals her frozen kiss on lilac
fz=frame(END_FZ)
crop=fz.crop((940-300,0,940+300,600)).resize((1000,1000),Image.LANCZOS)
rng=np.random.default_rng(5); minis=[(rng.uniform(200,1720),rng.uniform(0.6,1.2),rng.uniform(24,60),rng.uniform(0,6)) for _ in range(14)]
NE=120
for j in range(NE):
    t=j/FPS; img=LIL.copy().convert('RGBA')
    # mini hearts floating
    for x0,sp,ms,ph in minis:
        y=1120-((t*sp*220+ph*140)%1300); a=int(140*min(1,t*3))
        hm=heart_mask(x0+20*math.sin(t*2+ph),y,ms)
        img.paste(Image.new('RGBA',(W,H),WHITE+(a,)),(0,0),hm.point(lambda v:int(v*a/255)))
    s=3600 if j==0 else 600+(3600-600)*(1-ease(j/12))
    s*=1+0.04*math.sin(max(0,t-0.4)*6) if j>12 else 1
    cx,cy=960,420
    sh=heart_mask(cx+10,cy+24,s,blur=22).point(lambda v:int(v*0.45))
    img.paste(Image.new('RGBA',(W,H),(70,40,110,255)),(0,0),sh)
    ring=heart_mask(cx,cy,s+26)
    img.paste(Image.new('RGBA',(W,H),WHITE+(255,)),(0,0),ring)
    win=Image.new('RGB',(W,H)); cw=int(s*1.15); cimg=crop.resize((cw,cw),Image.LANCZOS); win.paste(cimg,(int(cx-cw/2),int(cy-cw/2+s*0.03)))
    img.paste(win,(0,0),heart_mask(cx,cy,s))
    L=Image.new('RGBA',(W,H),(0,0,0,0)); d=ImageDraw.Draw(L)
    for txt,font,y,t0,col in [('and yes, it was cringe for me to ask for that',F('fredoka600.ttf',54),835,0.45,PLUM),('so… thank you',F('titan.ttf',130),945,1.9,WHITE)]:
        u=(t-t0)/0.35
        if u<=0: continue
        sc=back(u); b=d.textbbox((0,0),txt,font=font); T=Image.new('RGBA',(b[2]-b[0]+40,b[3]-b[1]+40),(0,0,0,0)); ImageDraw.Draw(T).text((20-b[0],20-b[1]),txt,font=font,fill=col+(255,))
        T=T.resize((max(2,int(T.width*sc)),max(2,int(T.height*sc))),Image.LANCZOS)
        shd=Image.new('RGBA',T.size,(60,30,90,0)); shd.putalpha(T.split()[3].point(lambda v:int(v*0.4))); shd=shd.filter(ImageFilter.GaussianBlur(6))
        L.alpha_composite(shd,(int(960-T.width/2)+3,int(y-T.height/2)+6)); L.alpha_composite(T,(int(960-T.width/2),int(y-T.height/2)))
    if t>0.85:
        e=MONKEY.resize((max(2,int(64*back((t-0.85)/0.3))),)*2,Image.LANCZOS); L.alpha_composite(e,(int(960+560),int(835-e.height/2)))
    if t>2.25:
        e=HEARTE.resize((max(2,int(90*back((t-2.25)/0.3))),)*2,Image.LANCZOS); L.alpha_composite(e,(int(960+500),int(945-e.height/2)))
    img.alpha_composite(L); save(img)
print(k)
