from PIL import Image, ImageDraw, ImageFont, ImageFilter
import numpy as np, glob, os, math, random
random.seed(7)
W,H=1920,1080; FPS=30
def ease(x): x=max(0,min(1,x)); return 1-(1-x)**3
def back(x):
    x=max(0,min(1,x)); c=1.7; return 1+(c+1)*(x-1)**3+c*(x-1)**2
cf=sorted(glob.glob('cf/*.png')); bfs=sorted(glob.glob('bf/*.png'))
freeze=Image.open(cf[-1]).convert('RGBA')
bowl=Image.open('bowl_cut.png'); BW=330; bowl=bowl.resize((BW,int(BW*bowl.height/bowl.width)),Image.LANCZOS)
BC=(864,425)
T_POP=0.10; T_CUR=0.55; T_CLICK=1.10; T_BURST=1.25; T_SWITCH=1.55; T_END_P=2.25
# particles
spr=[Image.open(f) for f in sorted(glob.glob('pieces/*.png'))]
P=[]
for i in range(42):
    s=spr[i%len(spr)]
    ang=random.uniform(0,2*math.pi); sp=random.uniform(1300,2500)
    vx=math.cos(ang)*sp; vy=math.sin(ang)*sp*0.8-500
    P.append(dict(img=s,x=BC[0]+random.uniform(-50,50),y=BC[1]+random.uniform(-30,30),vx=vx,vy=vy,rot=random.uniform(0,360),vr=random.uniform(-500,500),s0=random.uniform(0.6,1.0),d=random.uniform(0,0.08)))
OATC=[(196,168,120),(180,150,104),(210,186,142)]
O=[]
for i in range(55):
    ang=random.uniform(0,2*math.pi); sp=random.uniform(1500,2700)
    O.append(dict(x=BC[0],y=BC[1],vx=math.cos(ang)*sp,vy=math.sin(ang)*sp*0.8-400,r=random.uniform(7,14),c=random.choice(OATC),a=random.uniform(0,180),d=random.uniform(0,0.1)))
def particles(img,t):
    dt=t-T_BURST
    if dt<0 or t>T_SWITCH+0.25: return img
    L=Image.new('RGBA',(W,H),(0,0,0,0)); d=ImageDraw.Draw(L)
    for o in O:
        u=dt-o['d']
        if u<0: continue
        sc=1+2.2*u; x=o['x']+o['vx']*u; y=o['y']+o['vy']*u+800*u*u
        rx=o['r']*sc; ry=rx*0.6
        al=int(255*max(0,min(1,1-(u-0.35)/0.25)))
        if al>0: d.ellipse((x-rx,y-ry,x+rx,y+ry),fill=o['c']+(al,))
    for p in P:
        u=dt-p['d']
        if u<0: continue
        sc=p['s0']*(1+2.0*u); x=p['x']+p['vx']*u; y=p['y']+p['vy']*u+900*u*u
        if x<-400 or x>W+400 or y>H+400: continue
        im=p['img']; im=im.resize((max(2,int(im.width*sc)),max(2,int(im.height*sc))),Image.BILINEAR).rotate(p['rot']+p['vr']*u,expand=True,resample=Image.BICUBIC)
        L.alpha_composite(im,(int(x-im.width/2),int(y-im.height/2)))
    sh=Image.new('RGBA',(W,H),(0,0,0,0)); sh.putalpha(L.split()[3].point(lambda v:int(v*0.35)))
    sh=sh.filter(ImageFilter.GaussianBlur(8))
    img=Image.alpha_composite(img,sh); return Image.alpha_composite(img,L)
def cursor_img(s=1.0):
    pts=[(0,0),(0,34),(9,26),(15,40),(21,37),(15,24),(27,24)]
    im=Image.new('RGBA',(70,90),(0,0,0,0)); d=ImageDraw.Draw(im)
    d.polygon([(x*2+4,y*2+4) for x,y in pts],fill=(255,255,255,255),outline=(0,0,0,255),width=4)
    return im if s==1 else im.resize((int(70*s),int(90*s)),Image.LANCZOS)
def bowl_layer(img,t):
    if t<T_POP: return img
    sc=back((t-T_POP)/0.30)
    if T_CLICK<=t<T_CLICK+0.15: sc*=1-0.12*math.sin((t-T_CLICK)/0.15*math.pi)
    if t>=T_BURST: sc*=1+0.06*math.sin((t-T_BURST)*40)*max(0,1-(t-T_BURST)/0.3)
    bob=4*math.sin(t*5)
    im=bowl.resize((max(2,int(bowl.width*sc)),max(2,int(bowl.height*sc))),Image.LANCZOS)
    sh=Image.new('RGBA',(W,H),(0,0,0,0)); ss=Image.new('RGBA',im.size,(0,0,0,120)); sh.paste(ss,(int(BC[0]-im.width/2)+6,int(BC[1]-im.height/2+bob)+14),im)
    img=Image.alpha_composite(img,sh.filter(ImageFilter.GaussianBlur(10)))
    img.alpha_composite(im,(int(BC[0]-im.width/2),int(BC[1]-im.height/2+bob)))
    if T_CLICK<=t<T_CLICK+0.45:
        k=(t-T_CLICK)/0.45; r=int(40+200*k)
        ring=Image.new('RGBA',(W,H),(0,0,0,0)); ImageDraw.Draw(ring).ellipse((BC[0]-r,BC[1]-r,BC[0]+r,BC[1]+r),outline=(255,255,255,int(255*(1-k))),width=6)
        img=Image.alpha_composite(img,ring)
    return img
def cursor_layer(img,t):
    if t<T_CUR or t>T_BURST+0.1: return img
    p=ease((t-T_CUR)/0.5); sx,sy=1450,1000; tx,ty=BC[0]+40,BC[1]+20
    s=0.82 if T_CLICK-0.03<=t<T_CLICK+0.12 else 1.0
    img.alpha_composite(cursor_img(s),(int(sx+(tx-sx)*p),int(sy+(ty-sy)*p))); return img
# title
tf=ImageFont.truetype('inter800.ttf',74)
lines=[('second things',[('second',0.75),('things',0.90)]),('second,',[('second,',1.05)]),('breakfast',[('breakfast',1.35)])]
d0=ImageDraw.Draw(Image.new('RGB',(10,10))); words=[]; y=630
for ln,ws in lines:
    x=290-d0.textlength(ln,font=tf)/2
    for w,tt in ws: words.append((w,x,y,tt)); x+=d0.textlength(w+' ',font=tf)
    y+=92
def title(img,tb):
    T=Image.new('RGBA',(W,H),(0,0,0,0)); dt=ImageDraw.Draw(T); a=False
    for w,x,y,tt in words:
        if tb>=tt: dt.text((x,y),w,font=tf,fill=(255,255,255,255)); a=True
    if not a: return img
    gl=Image.new('RGBA',(W,H),(255,255,255,0)); gl.putalpha(T.filter(ImageFilter.GaussianBlur(18)).split()[3].point(lambda v:min(255,int(v*1.4))))
    sh=Image.new('RGBA',(W,H),(0,0,0,0)); sh.putalpha(T.split()[3].point(lambda v:int(v*0.4))); sh=sh.filter(ImageFilter.GaussianBlur(6))
    return Image.alpha_composite(img,Image.alpha_composite(Image.alpha_composite(gl,sh),T))
os.makedirs('p5f',exist_ok=True); [os.remove(f) for f in glob.glob('p5f/*')]
k=0
for i in range(34,len(cf)):
    os.symlink(f'../cc/{i:04d}.png',f'p5f/{k:04d}.png'); k+=1
nf=int(round(T_SWITCH*FPS))
for j in range(nf):
    t=j/FPS
    img=freeze.copy(); img=bowl_layer(img,t); img=cursor_layer(img,t); img=particles(img,t)
    img.convert('RGB').save(f'p5f/{k:04d}.png'); k+=1
for j in range(len(bfs)):
    t=T_SWITCH+j/FPS
    img=Image.open(bfs[j]).convert('RGBA')
    if False:
        f=bowl_layer(freeze.copy(),t); img=Image.blend(f,img,(j+1)/3)
    img=particles(img,t); img=title(img,j/FPS)
    img.convert('RGB').save(f'p5f/{k:04d}.png'); k+=1
print(k, nf)
