from PIL import Image, ImageDraw, ImageFont, ImageFilter
import numpy as np, math, os, glob, random
from office_txt import torn_label, ring
W,H=1920,1080; FPS=30
LILAC=(201,179,236); LILD=(122,100,158); PLUM=(74,52,110); WHITE=(255,255,255)
def ease(x): x=max(0,min(1,x)); return 1-(1-x)**3
def back(x):
    x=max(0,min(1,x)); c=1.7; return 1+(c+1)*(x-1)**3+c*(x-1)**2
F=lambda n,s: ImageFont.truetype(n,s)
fred=F('fredoka600.ttf',44); fredh=F('fredoka600.ttf',52); titan=F('titan.ttf',120); corm=F('corm600i.ttf',96)
inter=F('inter800.ttf',64); thin=F('inter300.ttf',60)
emo=ImageFont.truetype('/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf',109)
def emoji(ch,size):
    im=Image.new('RGBA',(160,160),(0,0,0,0)); ImageDraw.Draw(im).text((10,10),ch,font=emo,embedded_color=True)
    im=im.crop(im.getbbox()); return im.resize((size,int(size*im.height/im.width)),Image.LANCZOS)
BOW=emoji('🎀',110)
def shadowed(T,blur=6,op=0.45,col=(40,25,70)):
    sh=Image.new('RGBA',T.size,col+(0,)); sh.putalpha(T.split()[3].point(lambda v:int(v*op))); sh=sh.filter(ImageFilter.GaussianBlur(blur))
    o=Image.new('RGBA',T.size,(0,0,0,0)); o.alpha_composite(sh,(0,0)); 
    s2=Image.new('RGBA',T.size,(0,0,0,0)); s2.alpha_composite(sh,(4,6)); return Image.alpha_composite(s2,T)
def glow(T,col=(201,179,236)):
    gl=Image.new('RGBA',T.size,col+(0,)); gl.putalpha(T.filter(ImageFilter.GaussianBlur(16)).split()[3].point(lambda v:min(255,int(v*1.5))))
    return Image.alpha_composite(gl,shadowed(T))
def pop_word(L,txt,font,cx,cy,u,col,anchor='mm',rot=0):
    if u<=0: return
    s=back(u); a=min(1,u*3)
    d=ImageDraw.Draw(Image.new('RGBA',(5,5))); b=d.textbbox((0,0),txt,font=font)
    T=Image.new('RGBA',(b[2]-b[0]+40,b[3]-b[1]+40),(0,0,0,0)); ImageDraw.Draw(T).text((20-b[0],20-b[1]),txt,font=font,fill=col+(255,))
    T=T.resize((max(2,int(T.width*s)),max(2,int(T.height*s))),Image.LANCZOS)
    if rot: T=T.rotate(rot,expand=True,resample=Image.BICUBIC)
    T.putalpha(T.split()[3].point(lambda v:int(v*a)))
    x=cx-T.width/2 if anchor[0]=='m' else cx-20*s
    L.alpha_composite(T,(int(x),int(cy-T.height/2)))

LILBG=(214,198,240)
def sink_card(img,sc,yoff_bottom=20):
    w=int(W*sc); h=int(H*sc); x0=(W-w)//2; y0=H-h-int(yoff_bottom*(1-sc)/0.34) if sc<0.999 else 0
    bg=Image.new('RGBA',(W,H),LILBG+(255,)); rad=int(36*min(1,(1-sc)/0.18))
    sh=Image.new('RGBA',(W,H),(0,0,0,0)); ImageDraw.Draw(sh).rounded_rectangle((x0+10,y0+22,x0+w+10,y0+h+22),rad,fill=(60,30,90,90))
    bg=Image.alpha_composite(bg,sh.filter(ImageFilter.GaussianBlur(24)))
    m=Image.new('L',(w,h),0); ImageDraw.Draw(m).rounded_rectangle((0,0,w-1,h-1),rad,fill=255)
    bg.paste(img.convert('RGB').resize((w,h),Image.LANCZOS),(x0,y0),m); return bg
def bounce(u):
    u=max(0,min(1,u)); return 1-math.cos(u*math.pi*2.5)*math.exp(-u*5)
# ---------- scene 1-2: to-do card
TODO=[("answering emails",12.2,13.0),("editing",13.4,14.2),("preparing content for 4 accounts",15.6,17.0)]
def todo(img,ct):
    if ct<11.75 or ct>22.25: return img
    p=back((ct-11.75)/0.4); out=1 if ct<21.9 else max(0,1-(ct-21.9)/0.35)
    cw,ch=600,420; card=Image.new('RGBA',(cw,ch),(0,0,0,0)); d=ImageDraw.Draw(card)
    d.rounded_rectangle((0,0,cw-1,ch-1),28,fill=(255,255,255,240),outline=LILAC+(255,),width=4)
    d.text((34,26),"today's to-do:",font=fredh,fill=PLUM)
    for i,(t,ta,tk) in enumerate(TODO):
        y=110+i*95
        if ct<ta: continue
        u=ease((ct-ta)/0.3); col=(60,45,80,int(255*u))
        d.rounded_rectangle((34,y+4,74,y+44),9,outline=LILD+(int(255*u),),width=4)
        lines=[t] if len(t)<20 else ["preparing content","for 4 accounts"]
        for j,l in enumerate(lines): d.text((92,y-2+j*46),l,font=fred,fill=col)
        if ct>=tk:
            v=min(1,(ct-tk)/0.2)
            d.line([(40,y+24),(40+12*v,y+36)],fill=LILD,width=7)
            if v>0.5: d.line([(52,y+36),(52+22*(v-0.5)*2,y+8+28*(1-(v-0.5)*2))],fill=LILD,width=7)
            if v>=1: d.line([(92,y+22),(92+min(1,(ct-tk-0.2)/0.3)*d.textlength(lines[0],font=fred),y+22)],fill=LILD+(200,),width=4)
    card=card.resize((max(2,int(cw*p)),max(2,int(ch*p))),Image.LANCZOS); card.putalpha(card.split()[3].point(lambda v:int(v*out)))
    sh=Image.new('RGBA',(W,H),(0,0,0,0)); 
    img=img.convert('RGBA'); x0=1600-card.width//2; y0=270-card.height//2
    s2=Image.new('RGBA',card.size,(60,30,90,int(80*out))); sh.paste(s2,(x0+10,y0+20),card)
    img=Image.alpha_composite(img,sh.filter(ImageFilter.GaussianBlur(20))); img.alpha_composite(card,(x0,y0)); return img
# ---------- scene 3: text behind her
def s3(img,ct,idx):
    if not (22.27<=ct<25.53): return img
    L=Image.new('RGBA',(W,H),(0,0,0,0))
    pop_word(L,"marketing &",F('titan.ttf',110),960,470,(ct-22.45)/0.35,LILAC)
    pop_word(L,"acquisition calls",F('titan.ttf',110),960,610,(ct-22.85)/0.35,LILAC)
    out=Image.alpha_composite(img.convert('RGBA'),shadowed(L,8,0.7))
    mp=f'm3/{idx:04d}.png'
    if False:
        m=Image.open(mp).convert('L').resize((W,H)).filter(ImageFilter.GaussianBlur(1.5)); out.paste(img.convert('RGB'),(0,0),m)
    return out
def s4(img,ct):
    if not (25.53<=ct<27.13): return img
    sc=1-0.18*bounce((ct-25.53)/0.5)
    img=sink_card(img,sc)
    L=Image.new('RGBA',(W,H),(0,0,0,0)); pop_word(L,"and some more…",F('titan.ttf',96),960,95,(ct-25.65)/0.3,LILAC)
    return Image.alpha_composite(img,shadowed(L,6,0.8))
def s5(img,ct):
    if not (27.13<=ct<30.1): return img
    sc=0.82-0.16*bounce((ct-27.13)/0.5)
    img=sink_card(img,sc)
    L=Image.new('RGBA',(W,H),(0,0,0,0)); f=F('titan.ttf',150)
    sh=5*math.sin(ct*55) if ct>27.6 else 0
    pop_word(L,"AND SOME MORE",f,960,175,(ct-27.2)/0.3,LILD,rot=sh)
    return Image.alpha_composite(img,shadowed(L,8,0.8))
def sticker_cut(img,idx,ct):
    mp=f'm6/{idx:04d}.png'
    m=Image.open(mp).convert('L').resize((W,H)) if os.path.exists(mp) else Image.new('L',(W,H),0)
    from scipy import ndimage as nd
    a=np.array(m)>110; a=nd.binary_opening(a,iterations=7); lab,n=nd.label(a)
    if n>1:
        sz=nd.sum(a,lab,range(1,n+1)); a=lab==(np.argmax(sz)+1)
    m=Image.fromarray((a*255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1))
    bg=Image.new('RGBA',(W,H),LILBG+(255,))
    outline=m.filter(ImageFilter.MaxFilter(19)).filter(ImageFilter.GaussianBlur(1.5))
    sh=Image.new('RGBA',(W,H),(60,30,90,0)); sh.putalpha(outline.point(lambda v:int(v*0.35))); sh=sh.filter(ImageFilter.GaussianBlur(14))
    bg.alpha_composite(sh,(8,14))
    wl=Image.new('RGBA',(W,H),(255,255,255,0)); wl.putalpha(outline); bg=Image.alpha_composite(bg,wl)
    bg.paste(img.convert('RGB'),(0,0),m)
    return bg
LAB24=torn_label('24 HOURS',11)
W6=[("more editing",30.3,1400,170,-3),("building AI automations",30.8,1400,300,2),("for my business",30.8,1400,370,2),("training my AI",31.3,1400,500,-2),("writing my next book",31.8,1470,630,3)]
def s6(img,ct,idx=0):
    if not (30.1<=ct<33.9): return img
    img=sticker_cut(img,idx,ct)
    L=Image.new('RGBA',(W,H),(0,0,0,0))
    if ct<32.35:
        for t,t0,x,y,r in W6: pop_word(L,t,F('titan.ttf',54),x,y,(ct-t0)/0.25,LILD,rot=r)
        img=Image.alpha_composite(img.convert('RGBA'),shadowed(L,5,0.35))
    else:
        T=Image.new('RGBA',(W,H),(0,0,0,0)); 
        pop_word(T,"yes. all at once.",F('titan.ttf',74),1400,240,(ct-32.4)/0.3,LILD)
        pop_word(T,"because a day only has",F('fredoka600.ttf',54),1400,345,(ct-32.75)/0.3,PLUM)
        img=Image.alpha_composite(img.convert('RGBA'),shadowed(T,5,0.3))
        u=(ct-33.05)/0.3
        if u>0:
            s=back(u); lb=LAB24.resize((max(2,int(LAB24.width*s)),max(2,int(LAB24.height*s))),Image.LANCZOS).rotate(ring(ct,33.4)-3,expand=True,resample=Image.BICUBIC)
            img.alpha_composite(lb,(int(1400-lb.width/2),int(470-lb.height/2)))
    return img
NB=Image.open('notebook_cut.png').convert('RGBA'); NB=NB.resize((230,int(230*NB.height/NB.width)),Image.LANCZOS)
def s7(img,ct):
    if ct<33.9: return img
    img=img.convert('RGBA')
    if ct<37.1:
        out=1 if ct<36.8 else max(0,1-(ct-36.8)/0.3)
        p=back((ct-34.0)/0.4)
        if p>0:
            pw,ph=1250,380; P=Image.new('RGBA',(pw,ph),(0,0,0,0)); d=ImageDraw.Draw(P)
            d.rounded_rectangle((0,0,pw-1,ph-1),30,fill=(246,239,252,245),outline=LILAC+(255,),width=4)
            d.text((50,60),"and yes… that's the exact opposite",font=F('fredoka600.ttf',54),fill=PLUM)
            d.text((50,135),"of what I teach in my notebook.",font=F('fredoka600.ttf',54),fill=PLUM)
            u=(ct-34.9)/0.35
            if u>0:
                s=back(u); nb=NB.resize((max(2,int(NB.width*s)),max(2,int(NB.height*s))),Image.LANCZOS).rotate(6,expand=True,resample=Image.BICUBIC)
                P.alpha_composite(nb,(int(1020-nb.width/2),int(ph/2-nb.height/2)))
                v=(ct-35.6)/0.25
                if v>0:
                    dd=ImageDraw.Draw(P); k=min(1,v)
                    dd.line([(930,90),(930+180*k,90+200*k)],fill=(200,60,90,255),width=16)
                    if v>1: dd.line([(1110,90),(1110-180*min(1,v-1),90+200*min(1,v-1))],fill=(200,60,90,255),width=16)
            P=P.resize((max(2,int(pw*min(1,p))),max(2,int(ph*min(1,p)))),Image.LANCZOS); P.putalpha(P.split()[3].point(lambda v:int(v*out)))
            img.alpha_composite(P,(int(960-P.width/2),int(540-P.height/2)))
    elif ct<39.0:
        L=Image.new('RGBA',(W,H),(0,0,0,0))
        pop_word(L,"but hey…",F('fredoka600.ttf',80),960,380,(ct-37.15)/0.3,WHITE)
        pop_word(L,"I'm just a girl",F('titan.ttf',150),900,560,(ct-37.6)/0.35,LILAC)
        img=Image.alpha_composite(img,shadowed(L,8,0.8))
        u=(ct-38.0)/0.3
        if u>0:
            s=back(u); b=BOW.resize((max(2,int(BOW.width*s*1.2)),max(2,int(BOW.height*s*1.2))),Image.LANCZOS).rotate(10*math.sin(ct*6),expand=True,resample=Image.BICUBIC)
            img.alpha_composite(b,(int(1540-b.width/2),int(560-b.height/2)))
    else:
        L=Image.new('RGBA',(W,H),(0,0,0,0))
        # rewind sticker
        u=(ct-39.05)/0.3
        if u>0:
            s=back(u); st=Image.new('RGBA',(220,110),(0,0,0,0)); d=ImageDraw.Draw(st)
            d.rounded_rectangle((0,0,219,109),55,fill=LILAC+(255,))
            for ox in (110,70): d.polygon([(ox,30),(ox,80),(ox-36,55)],fill=WHITE+(255,))
            d.polygon([(150,30),(150,80),(186,55)],fill=(0,0,0,0)) 
            st=st.resize((max(2,int(220*s)),max(2,int(110*s))),Image.LANCZOS); L.alpha_composite(st,(int(300-st.width/2),int(330-st.height/2)))
        # writing-on serif text: reveal left to right
        v=min(1,max(0,(ct-39.3)/0.9))
        if v>0:
            T=Image.new('RGBA',(W,H),(0,0,0,0)); ImageDraw.Draw(T).text((80,420),"back to editing",font=F('corm600i.ttf',120),fill=WHITE+(255,))
            m=Image.new('L',(W,H),0); ImageDraw.Draw(m).rectangle((0,0,80+int(820*v),H),fill=255)
            T.putalpha(Image.fromarray(np.minimum(np.array(T.split()[3]),np.array(m))))
            L=Image.alpha_composite(L,T)
        img=Image.alpha_composite(img,glow(L))
    return img
if __name__=='__main__':
    import sys
    files=sorted(glob.glob('o2/*.png'))
    a,b=int(sys.argv[1]),int(sys.argv[2])
    for i in range(a,min(b,len(files))):
        ct=11.6+i/FPS; img=Image.open(files[i]).convert('RGB')
        img=todo(img,ct); img=s3(img,ct,i); img=s4(img,ct); img=s5(img,ct); img=s6(img,ct,i); img=s7(img,ct)
        img.convert('RGB').save(f'o2x/{i:04d}.png')
