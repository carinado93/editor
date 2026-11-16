import sys, os, math, numpy as np, cv2
sys.path.insert(0,'/home/claude/w/wk2')
from fx import *
STATS=[('Meditation','30m',30),('Sports','2h 00m',120),('Editing','3h 00m',180),('Writing','3h 00m',180),('Marketing & client acquisition','2h 30m',150),('Telling Claude what to do','2h 30m',150)]
def fmt(m): m=int(round(m)); return f'{m}m' if m<60 else f'{m//60}h {m%60:02d}m'
FZ=246; fr=Wk(FZ); m=np.array(Image.open(f'{F}wk2/endmask_fix.png').convert('L')).astype(np.float32)/255
person=fr.copy(); person.putalpha(Image.fromarray((m*255).astype(np.uint8)))
DARK=(22,18,30)
def checker(alpha=40,sz=40):
    c=Image.new('RGBA',(W,H),(0,0,0,0)); d=ImageDraw.Draw(c)
    for y in range(0,H,sz):
        for x in range(0,W,sz):
            if (x//sz+y//sz)%2: d.rectangle([x,y,x+sz,y+sz],fill=(255,255,255,alpha))
    return c
CHK=checker()
def route_pts(x0,y0,w,h,n=300):
    t=np.linspace(0,1,n)
    x=x0+w*t; y=y0+h*(0.5+0.32*np.sin(t*2*math.pi*1.6)+0.12*np.sin(t*2*math.pi*4.3+1))
    return list(zip(x,y))
ICONS=['☕','🥣','🧴','💻','🧘','🏋️','✍️']
def draw_route(img,pts,p,width=12,icons=True,isz=56):
    k=max(2,int(len(pts)*p)); lay=Image.new('RGBA',(W,H),(0,0,0,0)); d=ImageDraw.Draw(lay)
    d.line(pts[:k],fill=LILAC+(255,),width=width,joint='curve')
    gl=lay.filter(ImageFilter.GaussianBlur(10)); img.alpha_composite(gl); img.alpha_composite(lay)
    d2=ImageDraw.Draw(img); x,y=pts[k-1]; d2.ellipse([x-14,y-14,x+14,y+14],fill=WHITE,outline=LILAC,width=5)
    if icons:
        for q,ic in enumerate(ICONS):
            f=q/(len(ICONS)-1)
            if p>=f:
                x,y=pts[min(len(pts)-1,int(f*(len(pts)-1)))]; s=eob((p-f)*8)
                e=emoji(ic,max(2,int(isz*s))); bg=Image.new('RGBA',(e.width+20,e.height+20),(0,0,0,0)); ImageDraw.Draw(bg).ellipse([0,0,bg.width-1,bg.height-1],fill=WHITE)
                bg.alpha_composite(e,(10,10)); img.alpha_composite(bg,(int(x-bg.width/2),int(y-bg.height-14)))
def wordmark(img,x,y,size=70,col=WHITE,text='CARINA'):
    f=fnt('inter800.ttf',size); tw=int(f.getlength(text))+40
    lay=Image.new('RGBA',(tw+60,size+40),(0,0,0,0)); ImageDraw.Draw(lay).text((20,10),text,font=f,fill=col)
    lay=lay.transform(lay.size,Image.AFFINE,(1,0.28,-10,0,1,0),Image.BICUBIC)
    img.alpha_composite(lay,(int(x-lay.width/2),int(y-lay.height/2)))
def kudos(img,j):   # j frames since start
    rng=np.random.default_rng(7)
    for q in range(0):
        st=q*1.2; k=j-st
        if k<0: continue
        x=rng.uniform(80,1840); sp=rng.uniform(28,44); y=H+60-k*sp; sz=int(rng.uniform(60,110))
        if y<-150: continue
        e=emoji('👍',sz).rotate(rng.uniform(-25,25),expand=True,resample=Image.BICUBIC); img.alpha_composite(e,(int(x),int(y)))
    if j>10: pill(img,W/2,1000,'give kudos & follow for part 2',fnt('titan.ttf',70),s=eob((j-10)/9))
def bg_dark(t,blur=False):
    b=fr.copy()
    if blur: b=b.filter(ImageFilter.GaussianBlur(int(18*t)+1))
    ov=Image.new('RGBA',(W,H),DARK+(int(215*t),)); b.alpha_composite(ov)
    c=CHK.copy(); c.putalpha(c.getchannel('A').point(lambda v:int(v*t))); b.alpha_composite(c); return b
# ----- E1 -----
def E1(j):
    t=eo(j/12); img=bg_dark(t)
    d=ImageDraw.Draw(img); lab=fnt('inter300.ttf',38); val=fnt('inter800.ttf',84)
    if j>8: 
        a=eo((j-8)/8); d.text((1480,95),'DAY ACTIVITY',font=fnt('inter800.ttf',40),fill=(220,210,240,int(255*a)),anchor='mm')
    for q,(l,v,mn) in enumerate(STATS):
        st=12+q*6; k=j-st
        if k<0: continue
        col,row=q%2,q//2; x=1060+col*450; y=140+row*165
        e=eo(k/9); xo=int(160*(1-e)); al=int(255*e)
        lab_=l if len(l)<18 else l.replace(' & ',' &\n',1) if False else l
        fl=lab if len(l)<20 else fnt('inter300.ttf',28)
        d.text((x+xo,y),l,font=fl,fill=(200,190,225,al))
        d.text((x+xo,y+44),fmt(mn*eo(k/14)),font=val,fill=(255,255,255,al))
    if j>52:
        draw_route(img,route_pts(1080,640,760,150),eo((j-52)/40))
    if j>88:
        a=eo((j-88)/10); pill(img,1480,870,'WORK  11h 00m',fnt('titan.ttf',64),s=eob((j-88)/10))
    img.alpha_composite(person)
    if j>96: wordmark(img,300,1010,64)
    if j>120: kudos(img,j-120)
    return img
# ----- E2 -----
def E2(j):
    t=eo(j/12); img=bg_dark(t*0.75,blur=True)
    cw,ch=700,840; card=Image.new('RGBA',(cw,ch),(0,0,0,0)); d=ImageDraw.Draw(card)
    d.rounded_rectangle([0,0,cw-1,ch-1],40,fill=(20,16,26,250))
    g=np.zeros((ch,cw,4),np.uint8); yy=np.linspace(0,1,ch)[:,None]
    a=np.clip((yy-0.72)/0.28,0,1); g[...,0]=LILAC[0]; g[...,1]=LILAC[1]; g[...,2]=LILAC[2]; g[...,3]=(a*200).astype(np.uint8)
    gm=Image.fromarray(g,'RGBA'); mk=Image.new('L',(cw,ch),0); ImageDraw.Draw(mk).rounded_rectangle([0,0,cw-1,ch-1],40,fill=255)
    gm.putalpha(Image.fromarray(np.minimum(np.array(gm.getchannel('A')),np.array(mk)))); card.alpha_composite(gm)
    d=ImageDraw.Draw(card); small=fnt('inter800.ttf',30); big=fnt('inter800.ttf',70); tiny=fnt('inter300.ttf',24)
    d.text((48,50),'Top Activity',font=small,fill=WHITE); d.text((48,95),'EDITING',font=fnt('titan.ttf',92),fill=LILAC)
    card.alpha_composite(emoji('🎬',110),(cw-170,50))
    rows=[('Total Work',11*60,'▲ 22%','vs. yesterday',True),('Total Day',13.5*60,'▲ 8%','vs. yesterday',True),('Coffees',2,'▲ 100%','vs. yesterday',True),('Breakdowns',0,'▼ 100%','vs. yesterday',False)]
    for q,(l,v,ch_,sub,up) in enumerate(rows):
        k=j-(22+q*7); y=250+q*135
        if k<0: continue
        e=eo(k/12); val=fmt(v*e) if v>10 else str(int(round(v*e))) if l!='Breakdowns' else str(int(round(3*(1-e))))
        d.text((48,y),l,font=small,fill=(230,225,240)); d.text((48,y+40),val,font=big,fill=WHITE)
        cl=(140,230,160) if up else (255,140,140)
        tri=[(cw-215,y+30),(cw-195,y+5),(cw-175,y+30)] if up else [(cw-215,y+8),(cw-195,y+33),(cw-175,y+8)]
        d.polygon(tri,fill=cl); d.text((cw-162,y+18),ch_[2:],font=small,fill=WHITE,anchor='lm'); d.text((cw-215,y+48),sub,font=tiny,fill=(180,170,200))
    d.text((cw/2,ch-48),'DAY IN WORK 2026  ·  CARINA',font=fnt('inter800.ttf',32),fill=DARK,anchor='mm')
    e=eob(j/14); s=0.6+0.4*e; c2=card.resize((int(cw*s),int(ch*s)),Image.LANCZOS)
    img.alpha_composite(c2,(int(1480-c2.width/2),int(480-c2.height/2+300*(1-eo(j/14)))))
    img.alpha_composite(person)
    if j>120: kudos(img,j-120)
    return img
# ----- E3 -----
def phone_ui(p_tap=0,show_sticker=True):
    pw,ph=600,1020; ph_=Image.new('RGBA',(pw+40,ph+40),(0,0,0,0)); d=ImageDraw.Draw(ph_)
    d.rounded_rectangle([20,30,pw+20,ph+30],70,fill=(0,0,0,110)); ph_=ph_.filter(ImageFilter.GaussianBlur(14)); d=ImageDraw.Draw(ph_)
    d.rounded_rectangle([20,20,pw+20,ph+20],70,fill=(18,16,22,255)); d.rounded_rectangle([34,34,pw+6,ph+6],58,fill=(30,28,36,255))
    d.text((80,110),'Close',font=fnt('inter300.ttf',30),fill=WHITE,anchor='lm'); d.text((pw/2+20,110),'Share Activity',font=fnt('inter800.ttf',32),fill=WHITE,anchor='mm')
    sx0,sy0,sx1,sy1=90,170,pw-50,770
    sq=24
    for y in range(sy0,sy1,sq):
        for x in range(sx0,sx1,sq):
            d.rectangle([x,y,min(x+sq,sx1),min(y+sq,sy1)],fill=(70,68,76) if ((x-sx0)//sq+(y-sy0)//sq)%2 else (52,50,58))
    d.rectangle([sx0+18,sy0+18,sx0+200,sy0+56],outline=WHITE,width=2); d.text((sx0+109,sy0+37),'TRANSPARENT',font=fnt('inter300.ttf',20),fill=WHITE,anchor='mm')
    if show_sticker: ph_.alpha_composite(sticker_img(0.62),(int(sx0+(sx1-sx0)/2-sticker_img(0.62).width/2),sy0+70))
    for q in range(4): d.ellipse([pw/2+20-50+q*30-6,790,pw/2+20-50+q*30+6,802],fill=WHITE if q==1 else (120,120,120))
    d.text((80,850),'Share to',font=fnt('inter800.ttf',28),fill=WHITE)
    s=1+0.15*p_tap; r=int(48*s); cx,cy=140,940
    d.ellipse([cx-r-6,cy-r-6,cx+r+6,cy+r+6],fill=LILAC); d.ellipse([cx-r,cy-r,cx+r,cy+r],fill=(30,28,36)); d.ellipse([cx-r+10,cy-r+10,cx+r-10,cy+r-10],fill=LILD)
    d.text((cx,cy+r+28),'Story',font=fnt('inter300.ttf',22),fill=WHITE,anchor='mm')
    for q,lab in enumerate(['Copy','Save','Link','More']):
        x=280+q*95; d.ellipse([x-32,cy-32,x+32,cy+32],outline=WHITE,width=3); d.text((x,cy+r+28),lab,font=fnt('inter300.ttf',22),fill=WHITE,anchor='mm')
    return ph_
_ST={}
def sticker_img(s=1.0):
    if s in _ST: return _ST[s]
    w,h=700,900; im=Image.new('RGBA',(w,h),(0,0,0,0)); d=ImageDraw.Draw(im)
    lab=fnt('inter800.ttf',34); val=fnt('inter800.ttf',90)
    for q,(l,v) in enumerate([('Work','11h 00m'),('Sports','2h 00m'),('Meditation','30m')]):
        y=20+q*190; d.text((w/2,y),l,font=lab,fill=WHITE,anchor='ma'); d.text((w/2,y+46),v,font=val,fill=WHITE,anchor='ma')
    pts=route_pts(150,600,400,160,200); d.line(pts,fill=LILAC,width=14,joint='curve')
    wordmark(im,w/2,840,64)
    im=im.resize((int(w*s),int(h*s)),Image.LANCZOS); _ST[s]=im; return im
def E3(j):
    t=eo(j/12); img=bg_dark(t*0.75,blur=True)
    TAP=50; FLY=TAP+6
    if j<FLY+4:
        pt=0 if j<TAP else math.exp(-(j-TAP)/3)
        ph=phone_ui(pt,show_sticker=j<FLY)
        y=int(40+H*(1-eo(j/14)))
        img.alpha_composite(ph,(1180,y))
        if 30<=j<TAP+5:
            p=eo((j-30)/(TAP-32)); tgt=(1180+140+20,40+940+20); s_=(1700,1060)
            img.alpha_composite(cursor(0.82 if TAP-1<=j<=TAP+1 else 1),(int(s_[0]+(tgt[0]-s_[0])*p),int(s_[1]+(tgt[1]-s_[1])*p)))
    if j>=FLY:
        k=j-FLY; e=eo(k/14)
        phy=int(40+H*eo(k/10)); 
        if k<10: img.alpha_composite(phone_ui(0,False),(1180,phy))
        s=0.62+(1.0-0.62)*e; st=sticker_img(round(s,2))
        cx=1180+20+300+(1450-1500)*e; cy=40+170+70+st.height/2+(540-(40+170+70+st.height/2))*e
        sh=st.copy(); sh=Image.new('RGBA',st.size,(0,0,0,0)); sh.putalpha(st.getchannel('A').point(lambda v:int(v*0.5))); sh=sh.filter(ImageFilter.GaussianBlur(8))
        img.alpha_composite(sh,(int(cx-st.width/2+6),int(cy-st.height/2+10))); img.alpha_composite(st,(int(cx-st.width/2),int(cy-st.height/2)))
    img.alpha_composite(person)
    if j>120: kudos(img,j-120)
    return img
def cursor(s=1.0):
    pts=[(0,0),(0,34),(9,26),(15,40),(21,37),(15,24),(27,24)]
    im=Image.new('RGBA',(70,90),(0,0,0,0)); ImageDraw.Draw(im).polygon([(x*2+4,y*2+4) for x,y in pts],fill=(255,255,255,255),outline=(0,0,0,255),width=4)
    return im if s==1 else im.resize((int(70*s),int(90*s)),Image.LANCZOS)
V=sys.argv[1]; lo=int(sys.argv[2]) if len(sys.argv)>2 else 0; hi=int(sys.argv[3]) if len(sys.argv)>3 else 99999
d=f'{F}wk2/end{V}'+('b' if V=='3' else ''); os.makedirs(d,exist_ok=True); n=0; NE=185
fn={'1':E1,'2':E2,'3':E3}[V]
for i in range(209,FZ+1):
    if lo<=n<hi: Wk(i).convert('RGB').save(f'{d}/{n:04d}.png')
    n+=1
for j in range(NE):
    if lo<=n<hi: fn(j).convert('RGB').save(f'{d}/{n:04d}.png')
    n+=1
print(V,n)
