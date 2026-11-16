import os, math, glob, numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
W,H=1920,1080; FPS=30
LILAC=(201,179,236); LILD=(122,100,158); PLUM=(74,52,110); WHITE=(255,255,255)
F=lambda n,s: ImageFont.truetype('/home/claude/w/'+n,s)
emo=ImageFont.truetype('/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf',109)
def emoji(ch,size):
    im=Image.new('RGBA',(160,160),(0,0,0,0)); ImageDraw.Draw(im).text((10,10),ch,font=emo,embedded_color=True)
    im=im.crop(im.getbbox()); return im.resize((size,int(size*im.height/im.width)),Image.LANCZOS)
def ease(x): x=max(0,min(1,x)); return 1-(1-x)**3
def back(x): x=max(0,min(1,x)); c=1.7; return max(0.01,1+(c+1)*(x-1)**3+c*(x-1)**2)
def shadowed(T,blur=8,op=0.75,col=(40,25,70)):
    sh=Image.new('RGBA',T.size,col+(0,)); sh.putalpha(T.split()[3].point(lambda v:int(v*op))); sh=sh.filter(ImageFilter.GaussianBlur(blur))
    s2=Image.new('RGBA',T.size,(0,0,0,0)); s2.alpha_composite(sh,(4,6)); return Image.alpha_composite(s2,T)
def pop(L,txt,font,cx,cy,u,col):
    if u<=0: return
    s=back(u); a=min(1,u*3); d=ImageDraw.Draw(Image.new('RGBA',(5,5))); b=d.textbbox((0,0),txt,font=font)
    T=Image.new('RGBA',(b[2]-b[0]+40,b[3]-b[1]+40),(0,0,0,0)); ImageDraw.Draw(T).text((20-b[0],20-b[1]),txt,font=font,fill=col+(255,))
    T=T.resize((max(2,int(T.width*s)),max(2,int(T.height*s))),Image.LANCZOS); T.putalpha(T.split()[3].point(lambda v:int(v*a)))
    L.alpha_composite(T,(int(cx-T.width/2),int(cy-T.height/2)))
HEART=emoji('🤍',70); BELL=emoji('🔔',56); THUMB=emoji('👍',64)
def button(state,s):   # state 0 subscribe, 1 subscribed
    w,h=520,120; b=Image.new('RGBA',(w+20,h+24),(0,0,0,0)); d=ImageDraw.Draw(b)
    d.rounded_rectangle((10,18,w+10,h+18),h//2,fill=(60,30,90,90))
    b=b.filter(ImageFilter.GaussianBlur(8)); d=ImageDraw.Draw(b)
    if state==0:
        d.rounded_rectangle((10,10,w+10,h+10),h//2,fill=LILD+(255,)); d.text((10+w/2,10+h/2),'SUBSCRIBE',font=F('inter800.ttf',50),fill=WHITE,anchor='mm')
    else:
        d.rounded_rectangle((10,10,w+10,h+10),h//2,fill=(238,232,246,255)); d.text((10+w/2+35,10+h/2),'SUBSCRIBED',font=F('inter800.ttf',46),fill=PLUM,anchor='mm')
        b.alpha_composite(BELL,(40,10+h//2-BELL.height//2))
    return b.resize((max(2,int(b.width*s)),max(2,int(b.height*s))),Image.LANCZOS)
def likebtn(filled,s):
    w,h=220,120; b=Image.new('RGBA',(w+20,h+24),(0,0,0,0)); d=ImageDraw.Draw(b)
    d.rounded_rectangle((10,18,w+10,h+18),h//2,fill=(60,30,90,90)); b=b.filter(ImageFilter.GaussianBlur(8)); d=ImageDraw.Draw(b)
    d.rounded_rectangle((10,10,w+10,h+10),h//2,fill=(LILAC if filled else (238,232,246))+(255,))
    b.alpha_composite(THUMB,(10+w//2-THUMB.width//2,10+h//2-THUMB.height//2))
    return b.resize((max(2,int(b.width*s)),max(2,int(b.height*s))),Image.LANCZOS)
def cursor(s=1):
    pts=[(0,0),(0,34),(9,26),(15,40),(21,37),(15,24),(27,24)]
    im=Image.new('RGBA',(70,90),(0,0,0,0)); ImageDraw.Draw(im).polygon([(x*2+4,y*2+4) for x,y in pts],fill=(255,255,255,255),outline=(0,0,0,255),width=4)
    return im if s==1 else im.resize((int(70*s),int(90*s)),Image.LANCZOS)
src=sorted(glob.glob('/home/claude/w/cof/src/*.png')); FZ=20; N=int(3.8*FPS)
BLUR=None
LILBG=Image.new('RGBA',(W,H),(214,198,240,255)); _g=ImageDraw.Draw(LILBG)
for yy in range(H): _g.line([(0,yy),(W,yy)],fill=(int(220-14*yy/H),int(206-16*yy/H),int(244-8*yy/H),255))
k=0
def save(im):
    global k; im.convert('RGB').save(f'/home/claude/w/cof/out/{k:04d}.png'); k+=1
for i in range(FZ): save(Image.open(src[i]))
base=Image.open(src[FZ]).convert('RGBA')
SUBX,SUBY=1090,800; LIKX,LIKY=650,800; CL1=int(2.0*FPS); CL2=int(2.6*FPS)
for j in range(N):
    t=j/FPS
    # lilac fills from centre (iris) over 0.3s, closes over last 0.35s
    r_in=ease(t/0.3); r_out=ease((t-3.45)/0.35) if t>3.45 else 0
    R=int(1150*(r_in*(1-r_out)))
    bl=BLUR
    mask=Image.new('L',(W,H),0); ImageDraw.Draw(mask).ellipse((960-R,540-R,960+R,540+R),fill=255); mask=mask.filter(ImageFilter.GaussianBlur(30))
    img=LILBG.copy()
    L=Image.new('RGBA',(W,H),(0,0,0,0))
    pop(L,'any support in the form of',F('fredoka600.ttf',64),960,300,(t-0.25)/0.3,PLUM)
    pop(L,'a subscribe or like',F('titan.ttf',120),960,430,(t-0.5)/0.3,WHITE)
    pop(L,'would be highly appreciated',F('fredoka600.ttf',64),930,570,(t-0.85)/0.3,PLUM)
    img.alpha_composite(shadowed(L,8,0.45))
    u=(t-1.1)/0.3
    if u>0:
        h=back(u); img.alpha_composite(HEART.resize((max(2,int(70*h)),max(2,int(HEART.height*h)))),(int(930+435),int(570-35*h)))
        sub=button(1 if j>=CL1 else 0, back(u)*(1+0.12*math.exp(-(j-CL1)/3) if j>=CL1 else 1))
        img.alpha_composite(sub,(int(SUBX-sub.width/2),int(SUBY-sub.height/2)))
        lk=likebtn(j>=CL2, back(u)*(1+0.25*math.exp(-(j-CL2)/3) if j>=CL2 else 1))
        img.alpha_composite(lk,(int(LIKX-lk.width/2),int(LIKY-lk.height/2)))
    # cursor: to subscribe then like
    if 1.4<=t<3.0:
        if t<2.0: p=ease((t-1.4)/0.55); x=1700+(SUBX+40-1700)*p; y=1050+(SUBY+20-1050)*p
        elif t<2.6: p=ease((t-2.05)/0.5); x=SUBX+40+(LIKX+20-SUBX-40)*p; y=SUBY+20
        else: x=LIKX+20; y=SUBY+20
        cs=0.82 if (abs(j-CL1)<=1 or abs(j-CL2)<=1) else 1
        img.alpha_composite(cursor(cs),(int(x),int(y)))
    out=base.copy(); out.paste(img,(0,0),mask); img=out
    save(img)
for i in range(FZ+1,len(src)): save(Image.open(src[i]))
print(k,N)
