from PIL import Image, ImageDraw, ImageFont, ImageFilter
import numpy as np, glob, os, math, random
random.seed(5)
W,H=1920,1080
A=sorted(glob.glob('c4a/*.png')); B=sorted(glob.glob('c4b/*.png'))
frames=[(f,'a') for f in A]+[(f,'b') for f in B]+[(f,'c') for f in sorted(glob.glob('c4c/*.png'))]
CUT=len(A); C=(860,470)
TT=ImageFont.truetype('titan.ttf',118)
def ease_(x): x=max(0,min(1,x)); return 1-(1-x)**3
def eio_(x): x=max(0,min(1,x)); return x*x*(3-2*x)
def back_(x):
    x=max(0,min(1,x)); c=1.7; return 1+(c+1)*(x-1)**3+c*(x-1)**2
GOLD=[(255,214,120),(255,236,170),(255,196,80),(255,250,220)]
EXP0=CUT-8   # explosion starts 8 frames before cut
parts=[]
# gather sparkles (converge) before explosion
for i in range(60):
    ang=random.uniform(0,2*math.pi); r=random.uniform(150,420)
    parts.append(dict(kind='g',born=EXP0-6,life=7,x0=C[0]+math.cos(ang)*r*1.3,y0=C[1]+math.sin(ang)*r,size=random.uniform(2,4),star=random.random()<0.3,col=random.choice(GOLD),tw=random.uniform(0,6)))
# explosion sparkles
for i in range(260):
    ang=random.uniform(0,2*math.pi); sp=random.uniform(35,120)
    parts.append(dict(kind='e',born=EXP0+random.uniform(0,3),life=random.uniform(14,30),x0=C[0],y0=C[1],vx=math.cos(ang)*sp*1.3,vy=math.sin(ang)*sp,size=random.uniform(3,9),star=random.random()<0.4,col=random.choice(GOLD),tw=random.uniform(0,6)))
# residual sparkles on her
for i in range(55):
    ang=random.uniform(0,2*math.pi); r=random.uniform(0,260)
    parts.append(dict(kind='r',born=CUT+random.uniform(-1,6),life=random.uniform(10,20),x0=C[0]-40+math.cos(ang)*r*1.2,y0=C[1]+60+math.sin(ang)*r,vx=random.uniform(-2,2),vy=random.uniform(-3,-0.5),size=random.uniform(2,5),star=random.random()<0.35,col=random.choice(GOLD),tw=random.uniform(0,6)))
yy,xx=np.mgrid[0:H,0:W]
def draw(acc,x,y,size,col,a,star):
    r=int(size*6)+2; x0,x1=max(0,int(x)-r),min(W,int(x)+r); y0,y1=max(0,int(y)-r),min(H,int(y)+r)
    if x0>=x1 or y0>=y1: return
    dx=xx[y0:y1,x0:x1]-x; dy=yy[y0:y1,x0:x1]-y
    g=np.exp(-(dx*dx+dy*dy)/(2*size*size))+0.35*np.exp(-(dx*dx+dy*dy)/(2*(size*3)**2))
    if star: g+=np.exp(-(dy*dy)/(0.6*size*size))*np.exp(-np.abs(dx)/(size*3))+np.exp(-(dx*dx)/(0.6*size*size))*np.exp(-np.abs(dy)/(size*3))
    acc[y0:y1,x0:x1]+=g[...,None]*np.array(col,np.float32)*a
def zoomblur(img,amt,c):
    if amt<=0.002: return img
    pil=Image.fromarray(np.clip(img,0,255).astype(np.uint8)); acc=np.zeros_like(img); n=8
    for i in range(n):
        s=1+amt*i/(n-1); w,h=int(W*s),int(H*s)
        im=pil.resize((w,h),Image.BILINEAR); ox=int(c[0]*s-c[0]); oy=int(c[1]*s-c[1])
        acc+=np.asarray(im.crop((ox,oy,ox+W,oy+H))).astype(np.float32)
    return acc/n
os.makedirs('spk',exist_ok=True); [os.remove(f) for f in glob.glob('spk/*')]
D=np.hypot((xx-C[0])/1.25,yy-C[1])
for k,(f,_) in enumerate(frames):
    img=np.asarray(Image.open(f).convert('RGB')).astype(np.float32)
    acc=np.zeros_like(img)
    for p in parts:
        u=k-p['born']
        if u<0 or u>p['life']: continue
        tw=0.6+0.4*math.sin(u*1.3+p['tw'])
        if p['kind']=='g':
            q=u/p['life']; x=p['x0']+(C[0]-p['x0'])*q; y=p['y0']+(C[1]-p['y0'])*q; a=q*tw*1.2
        else:
            drag=1/(1+0.12*u) if p['kind']=='e' else 1
            x=p['x0']+p['vx']*u*drag; y=p['y0']+p['vy']*u*drag+0.25*u*u*(p['kind']=='e')
            a=(1-u/p['life'])*tw*1.3
        draw(acc,x,y,p['size'],p['col'],a,p['star'])
    rel=k-EXP0
    # explosion core: grows from 0 to big, peaks at the cut
    if rel>=0:
        if k<CUT:
            g=min(1,rel/8); R=90+420*g**1.4; inten=0.5+1.1*g
        else:
            g=(k-CUT); R=510+40*g; inten=1.6*math.exp(-g/2.0)
        core=np.exp(-(D/R)**2)*inten
        col=np.array([255,236,190],np.float32)
        img=img*(1-np.clip(core,0,1)[...,None]*0.85)+core[...,None]*col*0.95
    # zoom blur around cut (flashback style)
    if CUT-3<=k<CUT+6:
        zb=0.16*math.exp(-abs(k-CUT+0.5)/2.0)
        img=zoomblur(img,zb,C)
    out=img+acc*0.85
    rel2=k-CUT
    if rel2>=8:
        fr=Image.fromarray(np.clip(out,0,255).astype(np.uint8))
        if rel2<18: sc=1-(1-0.74)*ease_((rel2-8)/10)
        else: sc=0.74
        ta=1.0
        w=int(W*sc); h=int(H*sc); x0=(W-w)//2; y0=int(H-h-(1-sc)/0.26*30) if sc<0.999 else 0
        y0=min(y0,H-h)
        bg=Image.new('RGBA',(W,H),(250,232,165,255))
        rad=int(36*min(1,(1-sc)/0.26))
        shd=Image.new('RGBA',(W,H),(0,0,0,0)); ImageDraw.Draw(shd).rounded_rectangle((x0+10,y0+22,x0+w+10,y0+h+22),rad,fill=(120,90,30,90))
        bg=Image.alpha_composite(bg,shd.filter(ImageFilter.GaussianBlur(24)))
        m=Image.new('L',(w,h),0); ImageDraw.Draw(m).rounded_rectangle((0,0,w-1,h-1),rad,fill=255)
        bg.paste(fr.resize((w,h),Image.LANCZOS),(x0,y0),m)
        if rel2>=12 and ta>0:
            T=Image.new('RGBA',(W,H),(0,0,0,0)); dt=ImageDraw.Draw(T); SHL=Image.new('RGBA',(W,H),(0,0,0,0)); ds=ImageDraw.Draw(SHL)
            words=["let's","finish","breakfast"]; full=" ".join(words); tw=dt.textlength(full,font=TT); x=W/2-tw/2
            for wi,wd in enumerate(words):
                u=(rel2-12-wi*4)/8
                if u>0:
                    pp=back_(u); fs=ImageFont.truetype('titan.ttf',max(10,int(118*(0.5+0.5*pp))))
                    dx=(dt.textlength(wd,font=TT)-dt.textlength(wd,font=fs))/2; yy_=80-(1-ease_(u))*60
                    ds.text((x+dx+5,yy_+8),wd,font=fs,fill=(74,52,110,int(230*ta))); dt.text((x+dx,yy_),wd,font=fs,fill=(201,179,236,int(255*ta)))
                x+=dt.textlength(wd+' ',font=TT)
            bg=Image.alpha_composite(bg,Image.alpha_composite(SHL.filter(ImageFilter.GaussianBlur(4)),T))
        out=np.asarray(bg.convert('RGB')).astype(np.float32) if sc<0.999 else np.asarray(fr).astype(np.float32)
    Image.fromarray(np.clip(out,0,255).astype(np.uint8)).save(f'spk/{k:03d}.png')
print(len(frames),CUT)
