import sys, os, math; sys.path.insert(0,'/home/claude/w/spt'); os.chdir('/home/claude/w/spt')
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont, ImageFilter
W,H=1920,1080; F='/home/claude/w/'
ORG=(201,179,236); LILAC=(201,179,236); LILD=(122,100,158); WHITE=(255,255,255)
def eo(x): x=min(max(x,0),1); return 1-(1-x)**3
def ei(x): x=min(max(x,0),1); return x**3
def eob(x): x=min(max(x,0),1); c=1.7; return 1+(c+1)*(x-1)**3+c*(x-1)**2
def fnt(n,s): return ImageFont.truetype(F+n,s)
def R(i): return np.array(Image.open(f'fr/{min(i,505):04d}.png').convert('RGB')).astype(np.float32)
def SF(i):
    w=min(1,max(0,(i-481)/6)); return S(i)*(1-w)+R(i)*w
def S(i): return np.array(Image.open(f'outB/{min(i,505):04d}.png').convert('RGB')).astype(np.float32)
def Wk(i): return np.array(Image.open(f'/home/claude/w/wk2/fr/{max(1,i+1):04d}.png').convert('RGB')).astype(np.float32)
def zoom(img,cx,cy,z,blur=0):
    def one(zz):
        M=np.float32([[zz,0,W/2-zz*cx],[0,zz,H/2-zz*cy]]); return cv2.warpAffine(img,M,(W,H),flags=cv2.INTER_LINEAR,borderMode=cv2.BORDER_REFLECT)
    if blur<=0.002: return one(z)
    acc=np.zeros_like(img); n=8
    for k in range(n): acc+=one(z*(1+blur*k/n))
    return acc/n
def save(d,n,img):
    os.makedirs(d,exist_ok=True)
    if isinstance(img,np.ndarray): img=Image.fromarray(np.clip(img,0,255).astype(np.uint8))
    img.convert('RGB').save(f'{d}/{n:04d}.png')
PRE=list(range(460,488)); WORK_N=60
def work_tail(d,n,start=0):
    for i in range(start,WORK_N): save(d,n,Wk(i)); n+=1
    return n
# ---------- T1 zoom through arms into monitor ----------
def t1():
    d='/home/claude/w/wk2/t1'; n=0
    for i in PRE: save(d,n,S(i)); n+=1
    Z=16
    for j in range(Z):
        t=(j+1)/Z; z=1+11*ei(t); im=S(488+j)
        cx=W/2+(1155-W/2)*eo(t*1.3); cy=H/2+(415-H/2)*eo(t*1.3)
        out=zoom(im,cx,cy,z,0.25*t)
        if j>=Z-3: out=out*(1-(j-Z+4)/4*0.6)+255*(j-Z+4)/4*0.6
        save(d,n,out); n+=1
    Z2=14
    for j in range(Z2):
        t=(j+1)/Z2; z=1+5*(1-eo(t)); im=Wk(j)
        cx=1490+(W/2-1490)*eo(t); cy=580+(H/2-580)*eo(t)
        out=zoom(im,cx,cy,z,0.2*(1-t))
        if j<3: out=out*(0.4+0.2*j)+255*(0.6-0.2*j)
        save(d,n,out); n+=1
    return work_tail(d,n,Z2)
# ---------- T2 whip spin seated match ----------
def t2():
    d='/home/claude/w/wk2/t2'; n=0
    for i in PRE+list(range(488,498)): save(d,n,S(i)); n+=1
    def spin(img,ang,z,bl):
        acc=np.zeros_like(img); k=7
        for q in range(k):
            a=ang-bl*q/k; M=cv2.getRotationMatrix2D((W/2,H/2),a,z)
            acc+=cv2.warpAffine(img,M,(W,H),borderMode=cv2.BORDER_REFLECT)
        return acc/k
    for j in range(7):
        t=(j+1)/7; save(d,n,spin(S(498+j),-120*ei(t),1+0.35*t,40*t)); n+=1
    for j in range(8):
        t=(j+1)/8; save(d,n,spin(Wk(j),120*(1-eo(t)),1+0.35*(1-eo(t)),40*(1-t))); n+=1
    return work_tail(d,n,8)
# ---------- T3 workout paused card ----------
def card(p_btn=0):
    cw,ch=760,430; c=Image.new('RGBA',(cw+40,ch+50),(0,0,0,0)); dd=ImageDraw.Draw(c)
    dd.rounded_rectangle([20,30,cw+20,ch+30],36,fill=(0,0,0,90)); c=c.filter(ImageFilter.GaussianBlur(12)); dd=ImageDraw.Draw(c)
    dd.rounded_rectangle([20,20,cw+20,ch+20],36,fill=(255,255,255,255))
    dd.rounded_rectangle([20,20,cw+20,120],36,fill=ORG+(255,)); dd.rectangle([20,80,cw+20,120],fill=ORG+(255,))
    dd.rectangle([58,50,70,90],fill=WHITE); dd.rectangle([80,50,92,90],fill=WHITE)
    dd.text((120,70),'WORKOUT SAVED',font=fnt('inter800.ttf',46),fill=WHITE,anchor='lm')
    lab=fnt('inter300.ttf',30); val=fnt('inter800.ttf',54)
    for k,(l,v) in enumerate([('Time','2h 00m'),('Activities','3'),('Mood','reset')]):
        x=[60,340,560][k]; dd.text((x,165),l,font=lab,fill=(110,110,110)); dd.text((x,205),v,font=val,fill=LILD)
    s=1+0.12*p_btn
    bw,bh=int(520*s),int(96*s); bx=20+cw//2; by=360
    dd.rounded_rectangle([bx-bw//2,by-bh//2,bx+bw//2,by+bh//2],bh//2,fill=ORG+(255,))
    ff=fnt('inter800.ttf',int(44*s)); tl=ff.getlength('RESUME: WORK'); x0=bx-(tl+50*s)/2
    dd.text((x0,by),'RESUME: WORK',font=ff,fill=WHITE,anchor='lm'); tx_=x0+tl+22*s
    dd.polygon([(tx_,by-16*s),(tx_,by+16*s),(tx_+26*s,by)],fill=WHITE)
    return c
def cursor_img(s=1.0):
    pts=[(0,0),(0,34),(9,26),(15,40),(21,37),(15,24),(27,24)]
    im=Image.new('RGBA',(70,90),(0,0,0,0)); ImageDraw.Draw(im).polygon([(x*2+4,y*2+4) for x,y in pts],fill=(255,255,255,255),outline=(0,0,0,255),width=4)
    return im if s==1 else im.resize((int(70*s),int(90*s)),Image.LANCZOS)
def t3():
    d='/home/claude/w/wk2/t3'; n=0
    for i in PRE: save(d,n,SF(i)); n+=1
    fz=R(488); L=44; CL=30
    for j in range(L):
        dim=0.35*eo(j/8); gray=fz.mean(2,keepdims=True)
        b=(fz*(1-0.5*eo(j/8))+gray*0.5*eo(j/8))*(1-dim)
        img=Image.fromarray(b.astype(np.uint8)).convert('RGBA')
        pb=0 if j<CL else math.exp(-(j-CL)/3)*abs(math.cos((j-CL)*0.9))
        c=card(pb); sc=1.3*eob(j/10)
        c=c.resize((max(1,int(c.width*sc)),max(1,int(c.height*sc))),Image.LANCZOS)
        img.alpha_composite(c,(int(W/2-c.width/2),int(H/2-c.height/2+40)))
        tgt=(W/2+50,H/2-312+40+480)
        if 14<=j<CL+8:
            p=eo((j-14)/(CL-16)); sx,sy=1650,1000
            img.alpha_composite(cursor_img(0.82 if CL-1<=j<=CL+1 else 1),(int(sx+(tgt[0]-sx)*p),int(sy+(tgt[1]-sy)*p)))
        save(d,n,img); n+=1
    last=np.array(img.convert('RGB')).astype(np.float32)
    P=9
    for j in range(P):  # push left
        t=eo((j+1)/P); off=int(W*t)
        out=np.zeros_like(last); out[:,:W-off]=last[:,off:]; nw=Wk(j); out[:,W-off:]=nw[:,:off]
        k=int(60*(1-abs(2*t-1)))|1
        if k>1: out=cv2.blur(out,(k,1))
        save(d,n,out); n+=1
    return work_tail(d,n,P)
def ch_off(): return 255
# ---------- T4 rope: desk sticker ----------
def t4():
    import importlib; sys.argv=['x','0','0']
    src=open('rope.py').read().split('lo,hi=')[0]; g={}; exec(src,g)
    STK=g['STK']; rope_y=g['rope_y']; rot_paste=g['rot_paste']; pin=g['pin']
    fr=Wk(0); m=np.array(Image.open('/home/claude/w/wk2/mk/0001.png').convert('L').resize((W,H))).astype(np.float32)/255
    rgba=Image.fromarray(np.dstack([fr,np.clip((m-0.25)/0.5,0,1)*255]).astype(np.uint8),'RGBA'); bb=rgba.getbbox(); cut=rgba.crop(bb)
    sc=300/max(cut.size); cut=cut.resize((int(cut.width*sc),int(cut.height*sc)),Image.LANCZOS)
    pad=22; c=Image.new('RGBA',(cut.width+2*pad,cut.height+2*pad),(0,0,0,0)); c.paste(cut,(pad,pad),cut)
    a=c.getchannel('A').filter(ImageFilter.MaxFilter(17)).filter(ImageFilter.GaussianBlur(1.2))
    wh=Image.new('RGBA',c.size,(255,255,255,255)); wh.putalpha(a)
    sh=Image.new('RGBA',c.size,(0,0,0,0)); sh.putalpha(a.point(lambda v:int(v*0.45))); sh=sh.filter(ImageFilter.GaussianBlur(8))
    desk=Image.new('RGBA',(c.width+20,c.height+20),(0,0,0,0)); desk.alpha_composite(sh,(10,16)); desk.alpha_composite(wh); desk.alpha_composite(c)
    # label tag on sticker
    dl=ImageDraw.Draw(desk); f=fnt('titan.ttf',40); tw=f.getlength('WORK')
    dl.rounded_rectangle([desk.width/2-tw/2-18,desk.height-70,desk.width/2+tw/2+18,desk.height-18],24,fill=LILAC); dl.text((desk.width/2,desk.height-44),'WORK',font=f,fill=WHITE,anchor='mm')
    items=[('Z',300),('P',700),('Y',1100),('D',1520)]
    d='/home/claude/w/wk2/t4'; n=0
    for i in PRE: save(d,n,SF(i)); n+=1
    fz=R(488); L=40; CL=20
    tw_=(bb[2]-bb[0])/(desk.width-64-20); tx=(bb[0]+bb[2])/2; 
    for j in range(L):
        dim=0.3*eo(j/6) if j<CL else 0.3*(1-eo((j-CL)/12))
        img=Image.fromarray((fz*(1-dim)).astype(np.uint8)).convert('RGBA'); dd=ImageDraw.Draw(img)
        oy=0 if j<CL+3 else -260*eo((j-CL-3)/8)
        xe=-20+1960*eo(j/7); pts=[(x,rope_y(x)+oy) for x in np.linspace(-20,xe,80)]
        dd.line(pts,fill=(70,55,45,255),width=5); dd.line([(x,y-1) for x,y in pts],fill=(150,128,108,255),width=2)
        for q,(k,x) in enumerate(items):
            td=2+2*q
            if j<td: continue
            dt=(j-td)/30; py=rope_y(x)+oy; yy=py-(1-eo(dt/0.25))*300
            ang=14*math.exp(-dt*1.6)*math.sin(dt*7+q)+2.2*math.sin(j/30*2.2+q)
            st=STK[k] if k!='D' else desk
            if k=='D' and j>=CL:
                t=(j-CL)/(L-6-CL); e=eo(min(t,1)); s=1+(tw_*1.0-1)*e
                cx=x+(tx-x)*e; cyc=(py+st.height/2)+(((bb[1]+bb[3])/2)-(py+st.height/2))*e-160*math.sin(math.pi*e)
                rot_paste(img,st,cx,cyc-st.height*s/2,ang*(1-e),1.0,s); continue
            rot_paste(img,st,x,yy,ang,0.45 if k!='D' else 1)
            img.alpha_composite(pin,(int(x-11),int(yy-28)))
            if k!='D':
                cx_,cy_=x+70,yy+40; dd=ImageDraw.Draw(img); dd.ellipse([cx_-26,cy_-26,cx_+26,cy_+26],fill=LILAC); dd.line([(cx_-12,cy_),(cx_-3,cy_+10),(cx_+14,cy_-10)],fill=WHITE,width=6)
        tgt=(1530,rope_y(1520)+150)
        if CL<=j<CL+12:
            kq=(j-CL)/12; r=int(40+220*kq); ring=Image.new('RGBA',(W,H),(0,0,0,0))
            ImageDraw.Draw(ring).ellipse((tgt[0]-r,tgt[1]-r,tgt[0]+r,tgt[1]+r),outline=(255,255,255,int(255*(1-kq))),width=6); img.alpha_composite(ring)
        if 8<=j<CL+5:
            p=eo((j-8)/(CL-9)); img.alpha_composite(cursor_img(0.82 if CL-1<=j<=CL+1 else 1),(int(1700+(tgt[0]-1700)*p),int(1020+(tgt[1]-1020)*p)))
        out=np.array(img.convert('RGB')).astype(np.float32)
        if j>=L-8:  # dissolve to work: background first, sticker becomes her
            w=eo((j-(L-8))/7); out=out*(1-w)+Wk(0)*w
        save(d,n,out); n+=1
    return work_tail(d,n,1)
which=sys.argv[1]
print(which, {'1':t1,'2':t2,'3':t3,'4':t4}[which]())
