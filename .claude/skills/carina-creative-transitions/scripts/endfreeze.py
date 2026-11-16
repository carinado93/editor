from PIL import Image, ImageDraw, ImageFont, ImageFilter
import numpy as np, math, os
W,H=1920,1080; FPS=30; N=int(3.6*FPS)
bg=Image.open('last.png').convert('RGBA')
mk=Image.open('mask_last.png').convert('L').filter(ImageFilter.GaussianBlur(1.2)); person=bg.copy(); person.putalpha(mk)
ef=ImageFont.truetype('/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf',109)
def ease(x): x=max(0,min(1,x)); return 1-(1-x)**3
def sticker(ch,size):
    im=Image.new('RGBA',(160,160),(0,0,0,0)); ImageDraw.Draw(im).text((10,10),ch,font=ef,embedded_color=True)
    im=im.crop(im.getbbox()); im=im.resize((size,int(size*im.height/im.width)),Image.LANCZOS)
    pad=24; c=Image.new('RGBA',(im.width+2*pad,im.height+2*pad),(0,0,0,0)); c.paste(im,(pad,pad),im)
    a=c.split()[3].filter(ImageFilter.MaxFilter(15)).filter(ImageFilter.GaussianBlur(1.5))
    white=Image.new('RGBA',c.size,(255,255,255,255)); white.putalpha(a)
    sh=Image.new('RGBA',c.size,(0,0,0,0)); sh.putalpha(a.point(lambda v:int(v*0.45)))
    sh=sh.filter(ImageFilter.GaussianBlur(8))
    out=Image.new('RGBA',(c.width+20,c.height+20),(0,0,0,0))
    out.alpha_composite(sh,(10,16)); out.alpha_composite(white,(0,0)); out.alpha_composite(c,(0,0))
    return out
def rope_y(x): return 55+75*(1-((x-960)/1000)**2)
items=[('lipstick_cut.png',300,56),('notebook_cut.png',540,150),('phone_cut.png',805,78),('latte_clean.png',1110,120),('burger_cut.png',1400,190)]
def real(path,size):
    im=Image.open(path).convert('RGBA'); im=im.resize((size,int(size*im.height/im.width)),Image.LANCZOS)
    pad=30; c=Image.new('RGBA',(im.width+2*pad,im.height+2*pad),(0,0,0,0)); c.paste(im,(pad,pad),im)
    sh=Image.new('RGBA',c.size,(0,0,0,0)); sh.putalpha(c.split()[3].point(lambda v:int(v*0.5))); sh=sh.filter(ImageFilter.GaussianBlur(10))
    out=Image.new('RGBA',(c.width+20,c.height+20),(0,0,0,0)); out.alpha_composite(sh,(10,16)); out.alpha_composite(c,(0,0)); return out
stk=[real(c,s) for c,_,s in items]
pin=Image.new('RGBA',(22,48),(0,0,0,0)); dp=ImageDraw.Draw(pin)
dp.rounded_rectangle((2,0,20,46),5,fill=(196,150,104,255),outline=(120,84,54,255),width=2); dp.line((11,6,11,40),fill=(150,108,70,255),width=2)
tf=ImageFont.truetype('inter800.ttf',120)
words=[('first',1.2),('things',1.35),('first,',1.5),('coffee',1.85)]
dd=ImageDraw.Draw(bg)
l1='first things first,'; b1=dd.textbbox((0,0),l1,font=tf); x1=(W-(b1[2]-b1[0]))/2-b1[0]
b2=dd.textbbox((0,0),'coffee',font=tf); x2=(W-(b2[2]-b2[0]))/2-b2[0]
pos=[(x1,700),(x1+dd.textlength('first ',font=tf),700),(x1+dd.textlength('first things ',font=tf),700),(x2,840)]
def cursor_img(s=1.0):
    pts=[(0,0),(0,34),(9,26),(15,40),(21,37),(15,24),(27,24)]
    im=Image.new('RGBA',(70,90),(0,0,0,0)); d=ImageDraw.Draw(im)
    P=[(x*2+4,y*2+4) for x,y in pts]; d.polygon(P,fill=(255,255,255,255),outline=(0,0,0,255),width=4)
    if s!=1: im=im.resize((int(70*s),int(90*s)),Image.LANCZOS)
    return im
COF=items[3]; cof_tip=(COF[1]+10, rope_y(COF[1])+110)
os.makedirs('ef',exist_ok=True)
for fr in range(N):
    t=fr/FPS; img=bg.copy(); d=ImageDraw.Draw(img)
    # rope draw-in
    rp=ease(t/0.35); xe=-20+1960*rp
    pts=[(x,rope_y(x)) for x in np.linspace(-20,xe,80)]
    d.line(pts,fill=(70,55,45,255),width=5); d.line([(x,y-1) for x,y in pts],fill=(150,128,108,255),width=2)
    # stickers
    clicked = t>=2.65
    for i,((ch,x,s),st) in enumerate(zip(items,stk)):
        td=0.30+0.15*i
        if t<td: continue
        dt_=t-td; drop=ease(dt_/0.25); py=rope_y(x)
        ang=14*math.exp(-dt_*1.6)*math.sin(dt_*7+i)+2.2*math.sin(t*2.2+i*1.3)
        scale=1.0
        if i==3 and clicked:
            k=t-2.65; scale=1+0.28*math.exp(-k*4)*abs(math.cos(k*10))+0.08*min(1,k*4)
        im=st if scale==1 else st.resize((int(st.width*scale),int(st.height*scale)),Image.LANCZOS)
        big=Image.new('RGBA',(im.width*2+40,im.height*2+40),(0,0,0,0)); cx=big.width//2
        big.alpha_composite(im,(cx-im.width//2,cx-6))
        big=big.rotate(ang,resample=Image.BICUBIC,center=(cx,cx))
        yy=py-(1-drop)*300
        img.alpha_composite(big,(int(x-cx),int(yy-cx)))
        img.alpha_composite(pin,(int(x-11),int(yy-28)))
        if i==3 and clicked:
            k=t-2.65
            if k<0.5:
                r=int(40+220*k); a=int(255*(1-k/0.5))
                ring=Image.new('RGBA',(W,H),(0,0,0,0)); ImageDraw.Draw(ring).ellipse((x-r,py+95-r,x+r,py+95+r),outline=(255,255,255,a),width=6)
                img=Image.alpha_composite(img,ring)
    img=Image.alpha_composite(img,person)
    # text layer (drawn before stickers? stickers on top)
    T=Image.new('RGBA',(W,H),(0,0,0,0)); dt=ImageDraw.Draw(T)
    for (w,ts),(x,y) in zip(words,pos):
        if t>=ts:
            pop=1+0.12*max(0,1-(t-ts)/0.12)
            dt.text((x,y),w,font=tf,fill=(255,255,255,255))
    glow=T.filter(ImageFilter.GaussianBlur(18)); ga=glow.split()[3].point(lambda v:min(255,int(v*1.4)))
    gl=Image.new('RGBA',(W,H),(255,255,255,0)); gl.putalpha(ga)
    sh=Image.new('RGBA',(W,H),(0,0,0,0)); sh.putalpha(T.split()[3].point(lambda v:int(v*0.35))); sh=sh.filter(ImageFilter.GaussianBlur(6))
    img=Image.alpha_composite(img,Image.alpha_composite(Image.alpha_composite(gl,sh),T))
    # cursor
    if t>=2.0:
        p=ease((t-2.0)/0.6); sx,sy=1500,980; tx,ty=cof_tip
        cxp=sx+(tx-sx)*p; cyp=sy+(ty-sy)*p
        s=0.82 if 2.62<=t<2.75 else 1.0
        img.alpha_composite(cursor_img(s),(int(cxp),int(cyp)))
    img.convert('RGB').save(f'ef/{fr:03d}.png')
