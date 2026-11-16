import sys, os, math, numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont, ImageFilter
W,H=1920,1080; F='/home/claude/w/'
LILAC=(201,179,236); LILD=(122,100,158); WHITE=(255,255,255); RED=(235,64,70); YEL=(255,214,92)
def eo(x): x=min(max(x,0),1); return 1-(1-x)**3
def eob(x): x=min(max(x,0),1); c=1.7; return max(0.02,1+(c+1)*(x-1)**3+c*(x-1)**2)
def fnt(n,s): return ImageFont.truetype(F+n,s)
EMO=ImageFont.truetype('/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf',109)
def emoji(ch,size):
    im=Image.new('RGBA',(160,160),(0,0,0,0)); ImageDraw.Draw(im).text((10,10),ch,font=EMO,embedded_color=True)
    im=im.crop(im.getbbox()); return im.resize((size,int(size*im.height/im.width)),Image.LANCZOS)
def Wk(i): return Image.open(f'{F}wk2/fr/{i+1:04d}.png').convert('RGBA')
def shadow_text(d,xy,t,f,fill,sh=LILD,off=(4,6),anchor='la'):
    d.text((xy[0]+off[0],xy[1]+off[1]),t,font=f,fill=sh,anchor=anchor); d.text(xy,t,font=f,fill=fill,anchor=anchor)
def pill(img,x,y,text,f,bg=LILAC,fg=WHITE,s=1.0,pad=(34,18)):
    tw=f.getlength(text); bb=f.getbbox(text); th=bb[3]-bb[1]
    w,h=int(tw+2*pad[0]),int(th+2*pad[1])
    p=Image.new('RGBA',(w+12,h+12),(0,0,0,0)); d=ImageDraw.Draw(p)
    d.rounded_rectangle([6,10,w+6,h+10],h//2,fill=(60,40,90,80)); d.rounded_rectangle([6,6,w+6,h+6],h//2,fill=bg+(255,))
    d.text((6+w/2,6+h/2),text,font=f,fill=fg,anchor='mm')
    if s!=1: p=p.resize((max(1,int(p.width*s)),max(1,int(p.height*s))),Image.LANCZOS)
    img.alpha_composite(p,(int(x-p.width/2),int(y-p.height/2)))
# ---------- battery ----------
def battery_A(img,j,n):   # j in 0..n
    t=j/n; lvl=40-37*eo(t*1.1); col=tuple(int(a+(b-a)*min(1,t*1.4)) for a,b in zip(LILAC,RED))
    s=eob(j/8); blink= (t>0.8 and (j//3)%2==0)
    lay=Image.new('RGBA',(520,200),(0,0,0,0)); d=ImageDraw.Draw(lay)
    d.rounded_rectangle([10,40,330,170],34,outline=WHITE,width=12); d.rounded_rectangle([336,80,362,130],8,fill=WHITE)
    fw=int(296*lvl/100)
    if not blink: d.rounded_rectangle([24,54,24+max(fw,18),156],22,fill=col)
    f=fnt('titan.ttf',72); shadow_text(d,(395,105),f'{int(lvl)}%',f,WHITE,anchor='lm')
    lay=lay.resize((int(520*s),int(200*s)),Image.LANCZOS)
    img.alpha_composite(lay,(1880-lay.width,90))
    f2=fnt('fredoka700.ttf',54)
    if j>4: pill(img,1880-260,320,'energy level',f2,s=eob((j-4)/8))
def battery_B(img,j,n):
    t=j/n; lvl=40-37*eo(t*1.1)
    # vertical battery left of the screen, label
    lay=Image.new('RGBA',(260,520),(0,0,0,0)); d=ImageDraw.Draw(lay)
    d.rounded_rectangle([90,10,170,40],10,fill=WHITE); d.rounded_rectangle([30,34,230,500],40,outline=WHITE,width=14)
    fh=int(440*lvl/100); col=tuple(int(a+(b-a)*min(1,t*1.4)) for a,b in zip(LILAC,RED))
    d.rounded_rectangle([48,482-max(fh,26),212,482],28,fill=col)
    s=eob(j/8); lay=lay.resize((int(260*s*0.8),int(520*s*0.8)),Image.LANCZOS)
    img.alpha_composite(lay,(1640,170)); d2=ImageDraw.Draw(img)
    f=fnt('titan.ttf',64); shadow_text(d2,(1744,640),f'{int(lvl)}%',f,WHITE,anchor='mm')
    pill(img,1744,740,'brain battery',fnt('fredoka700.ttf',46),s=eob((j-4)/8) if j>4 else 0.01)
    if t>0.62:  # iOS low battery popup
        k=(j-0.62*n)/8; s2=eob(k)
        c=Image.new('RGBA',(820,330),(0,0,0,0)); dc=ImageDraw.Draw(c)
        dc.rounded_rectangle([10,18,810,322],46,fill=(0,0,0,70)); c=c.filter(ImageFilter.GaussianBlur(10)); dc=ImageDraw.Draw(c)
        dc.rounded_rectangle([10,10,810,310],46,fill=(250,248,252,245))
        dc.text((410,80),'Low Battery',font=fnt('inter800.ttf',58),fill=(25,25,25),anchor='mm')
        dc.text((410,150),'3% remaining',font=fnt('inter300.ttf',44),fill=(60,60,60),anchor='mm')
        dc.line([(10,200),(810,200)],fill=(210,205,215),width=3)
        dc.text((410,255),'connect to coffee',font=fnt('inter800.ttf',48),fill=LILD,anchor='mm')
        c=c.resize((max(1,int(820*s2*0.95)),max(1,int(330*s2*0.95))),Image.LANCZOS)
        img.alpha_composite(c,(int(1180-c.width/2),int(330-c.height/2)))
# ---------- code ----------
def code_A(img,j,n):
    v=int(847*eo(j/(n*0.85))); s=eob(j/8)
    f=fnt('titan.ttf',96); f2=fnt('fredoka700.ttf',50)
    lay=Image.new('RGBA',(900,300),(0,0,0,0)); d=ImageDraw.Draw(lay)
    d.text((20,40),'lines of code',font=f2,fill=WHITE,stroke_width=0)
    shadow_text(d,(20,110),f'{v:,}',f,WHITE)
    pill(lay,600,175,'</>',fnt('inter800.ttf',60))
    lay=lay.resize((int(900*s),int(300*s)),Image.LANCZOS); img.alpha_composite(lay,(1120,60))
SNIP=['if (tired) { keepGoing() }','const coffee = 3;','// why is this not working','fix_bug_final_v7()','while(!done) edit();']
POS=[(1180,120),(1330,300),(1140,470),(1420,640),(1250,820)]
def code_B(img,j,n):
    f=fnt('inter800.ttf',40)
    for q,(sn,(x,y)) in enumerate(zip(SNIP,POS)):
        st=q*5
        if j<st: continue
        k=j-st; nc=min(len(sn),int(k*2.2)); txt=sn[:nc]+('|' if (k//3)%2==0 and nc<len(sn) else '')
        s=eob(k/7); tw=f.getlength(sn)
        p=Image.new('RGBA',(int(tw+70),96),(0,0,0,0)); d=ImageDraw.Draw(p)
        d.rounded_rectangle([4,8,tw+64,92],22,fill=(40,30,60,90)); d.rounded_rectangle([0,0,tw+60,84],22,fill=(30,24,44,235))
        d.ellipse([18,30,34,46],fill=LILAC); d.text((46,42),txt,font=f,fill=LILAC if q%2 else WHITE,anchor='lm')
        p=p.resize((max(1,int(p.width*s)),max(1,int(p.height*s))),Image.LANCZOS)
        img.alpha_composite(p,(int(x),int(y)))
# ---------- clock ----------
def flip_digit(ch_old,ch_new,k,f,w=120,h=170):  # k 0..1
    c=Image.new('RGBA',(w,h),(0,0,0,0)); d=ImageDraw.Draw(c)
    def face(ch):
        fc=Image.new('RGBA',(w,h),(0,0,0,0)); dd=ImageDraw.Draw(fc); dd.rounded_rectangle([0,0,w-1,h-1],18,fill=LILAC+(255,))
        dd.text((w/2,h/2+4),ch,font=f,fill=WHITE,anchor='mm'); dd.line([(0,h/2),(w,h/2)],fill=LILD,width=4); return fc
    A,B=face(ch_old),face(ch_new)
    if k<=0: return A
    if k>=1: return B
    out=Image.new('RGBA',(w,h)); out.paste(B.crop((0,0,w,h//2)),(0,0)); out.paste(A.crop((0,h//2,w,h)),(0,h//2))
    if k<0.5:
        top=A.crop((0,0,w,h//2)); hh=max(1,int(h/2*(1-2*k))); out.paste(top.resize((w,hh)),(0,h//2-hh))
    else:
        bot=B.crop((0,h//2,w,h)); hh=max(1,int(h/2*(2*k-1))); out.paste(bot.resize((w,hh)),(0,h//2))
    return out
def clock_A(img,j,n):
    f=fnt('titan.ttf',130); old='18:00'; new='21:47'
    lay=Image.new('RGBA',(5*130+40,190),(0,0,0,0)); x=0
    for q,(a,b) in enumerate(zip(old,new)):
        if a==':': ImageDraw.Draw(lay).text((x+30,95),':',font=f,fill=WHITE,anchor='mm'); x+=60; continue
        k=(j-6-q*3)/6; lay.alpha_composite(flip_digit(a,b,k,f),(x,8)); x+=130
    s=eob(j/7); lay=lay.resize((int(lay.width*s),int(lay.height*s)),Image.LANCZOS)
    img.alpha_composite(lay,(int(1340-lay.width/2),90))
    if j>20: pill(img,1340,360,'wait… it’s night?',fnt('fredoka700.ttf',56),s=eob((j-20)/8))
def clock_B(img,j,n):
    t=j/n; d=ImageDraw.Draw(img)
    lay=Image.new('RGBA',(W,H),(0,0,0,0)); dl=ImageDraw.Draw(lay)
    # night tint creeping in
    tint=Image.new('RGBA',(W,H),(40,30,90,int(90*eo(t*1.5)))); img.alpha_composite(tint)
    cx,cy,R=1500,520,330
    a1=math.pi*(1.15+0.5*eo(t*1.3)); sx,sy=cx+R*math.cos(a1),cy+R*math.sin(a1)*0.8+200
    dl.ellipse([sx-60,sy-60,sx+60,sy+60],fill=YEL+(int(255*(1-eo(t*1.6))),))
    a2=math.pi*(1.95-0.5*eo((t-0.25)*1.6)); mx,my=cx+R*math.cos(a2)-80,cy+R*math.sin(a2)*0.8+60
    if t>0.2:
        al=int(255*eo((t-0.2)*3)); dl.ellipse([mx-60,my-60,mx+60,my+60],fill=(245,240,255,al)); dl.ellipse([mx-30,my-75,mx+80,my+35],fill=(0,0,0,0))
    img.alpha_composite(lay.filter(ImageFilter.GaussianBlur(1)))
    f=fnt('titan.ttf',120); v=int(18*60+(21*60+47-18*60)*eo(t*1.2)); tx=f'{v//60:02d}:{v%60:02d}'
    shadow_text(ImageDraw.Draw(img),(1340,150),tx,f,WHITE,anchor='mm')
    if j>18: pill(img,1340,300,'wait… it’s night?',fnt('fredoka700.ttf',52),s=eob((j-18)/8))
# ---------- power-off ----------
def poweroff_A(fr,j,n):   # fr PIL frame (last screen frame), returns image
    a=np.array(fr.convert('RGB')).astype(np.float32); out=np.zeros_like(a)
    if j<n*0.45:
        t=eo(j/(n*0.45)); h=max(4,int(H*(1-t))); im=cv2.resize(a,(W,h))*(1+1.2*t)
        y=H//2-h//2; out[y:y+h]=im
    elif j<n*0.75:
        t=eo((j-n*0.45)/(n*0.3)); w=max(6,int(W*(1-t))); h=max(4,int(6*(1-t))+4)
        out[H//2-h//2:H//2-h//2+h, W//2-w//2:W//2-w//2+w]=255
        out=cv2.GaussianBlur(out,(0,0),3)*1.6
    else:
        t=(j-n*0.75)/(n*0.25); r=max(1,int(10*(1-t)))
        cv2.circle(out,(W//2,H//2),r,(255,255,255),-1); out=cv2.GaussianBlur(out,(0,0),4)*2
    img=Image.fromarray(np.clip(out,0,255).astype(np.uint8)).convert('RGBA')
    return img
def glitch_B(fr,j):
    a=np.array(fr.convert('RGB')).astype(np.float32); rng=np.random.default_rng(j)
    sh=int(8+3*j); out=a.copy(); out[...,0]=np.roll(a[...,0],sh,1); out[...,2]=np.roll(a[...,2],-sh,1)
    for q in range(6):
        y=rng.integers(0,H-60); h=rng.integers(10,60); out[y:y+h]=np.roll(out[y:y+h],rng.integers(-120,120),1)
    out[::4]*=0.75
    return Image.fromarray(np.clip(out,0,255).astype(np.uint8)).convert('RGBA')
# ---------- build ----------
def build(V,d):
    os.makedirs(d,exist_ok=True); n=0
    def save(img):
        nonlocal n; img.convert('RGB').save(f'{d}/{n:04d}.png'); n+=1
    for i in range(0,18): save(Wk(i))
    seg=list(range(18,65))
    for q,i in enumerate(seg):
        img=Wk(i); (battery_A if V=='A' else battery_B)(img,q,len(seg)-1); save(img)
    seg=list(range(65,99))
    for q,i in enumerate(seg):
        img=Wk(i); (code_A if V=='A' else code_B)(img,q,len(seg)-1); save(img)
    seg=[i for i in range(99,119) for _ in (0,1)]   # half speed
    for q,i in enumerate(seg):
        img=Wk(i); (clock_A if V=='A' else clock_B)(img,q,len(seg)-1); save(img)
    for i in range(119,138): save(Wk(i))
    if V=='A':
        fr=Wk(140)
        for q in range(16): save(poweroff_A(fr,q,15))
        for q in range(14):
            img=Image.new('RGBA',(W,H),(0,0,0,255)); f=fnt('titan.ttf',110)
            s=eob(q/8); lay=Image.new('RGBA',(1200,220),(0,0,0,0)); shadow_text(ImageDraw.Draw(lay),(540,110),'logging off',f,LILAC,sh=LILD,anchor='mm')
            e=emoji('✌️',100); tw=f.getlength('logging off'); lay.alpha_composite(e,(int(600+tw/2+20),55))
            lay=lay.resize((max(1,int(1200*s)),max(1,int(220*s))),Image.LANCZOS); img.alpha_composite(lay,(int(W/2-lay.width/2),int(H/2-lay.height/2))); save(img)
        for i in range(209,251): save(Wk(i))
    else:
        for q,i in enumerate(range(138,150)):
            img=glitch_B(Wk(i),q); save(img)
        seg=list(range(150,209,2))
        for q,i in enumerate(seg):
            img=Wk(i); dots='.'*(1+(q//4)%3)
            pill(img,W/2,880,'logging off'+dots+' '*(3-len(dots)),fnt('titan.ttf',72),s=eob(q/7)); save(img)
        for i in range(209,251): save(Wk(i))
    return n
if __name__=='__main__': print(build(sys.argv[1],f'{F}wk2/fx{sys.argv[1]}'))
