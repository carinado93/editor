from PIL import Image, ImageDraw, ImageFilter, ImageFont
import math, os
W,H=1920,1080; FPS=30
T_OPEN=2.75; T_HOLD=3.05; T_EXP=3.50; T_FULL=3.90
def ease(x): x=max(0,min(1,x)); return 1-(1-x)**3
def back(x):
    x=max(0,min(1,x)); c=1.5; return 1+(c+1)*(x-1)**3+c*(x-1)**2
def lerp(a,b,p): return a+(b-a)*p
START=(1110,230); HOLD_C=(960,500); HOLD_W=1080
os.makedirs('tr',exist_ok=True)
n=int(round((T_FULL-T_OPEN)*FPS))
for k in range(n):
    t=T_OPEN+k/FPS
    efi=min(107,int(round(t*FPS)))
    bg=Image.open(f'ef/{efi:03d}.png').convert('RGBA')
    cfr=Image.open(f'cf/{k+1:04d}.png').convert('RGB')
    if t<T_HOLD:
        p=back((t-T_OPEN)/(T_HOLD-T_OPEN)); q=ease((t-T_OPEN)/(T_HOLD-T_OPEN))
        w=lerp(120,HOLD_W,p); cx=lerp(START[0],HOLD_C[0],q); cy=lerp(START[1],HOLD_C[1],q); bar=44*min(1,w/HOLD_W); rad=22; sh=1.0
    elif t<T_EXP:
        w=HOLD_W; cx,cy=HOLD_C; bar=44; rad=22; sh=1.0
    else:
        p=ease((t-T_EXP)/(T_FULL-T_EXP))
        w=lerp(HOLD_W,1040,p); cx=lerp(HOLD_C[0],580,p); bar=44*(1-p); h=w*9/16
        cy=lerp(HOLD_C[1],540+bar/2,p); rad=22+14*p; sh=1.0
    w=max(40,w); h=w*9/16; tot=h+bar
    x0=cx-w/2; y0=cy-tot/2
    # dim background slightly while window open
    dim=Image.new('RGBA',(W,H),(30,20,40,int(70*min(1,(t-T_OPEN)/0.3))))
    img=Image.alpha_composite(bg,dim)
    if t>=T_EXP:
        q=ease((t-T_EXP)/(T_FULL-T_EXP)); img=Image.blend(img,Image.new('RGBA',(W,H),(214,198,240,255)),q)
    win=Image.new('RGBA',(int(w),int(tot)),(0,0,0,0))
    content=cfr.resize((int(w),int(h)),Image.LANCZOS)
    m=Image.new('L',win.size,0); ImageDraw.Draw(m).rounded_rectangle((0,0,win.width-1,win.height-1),int(rad),fill=255)
    base=Image.new('RGBA',win.size,(246,239,229,255)); dw=ImageDraw.Draw(base)
    if bar>4:
        r=bar*0.18
        for i,col in enumerate([(232,106,94),(240,190,80),(110,190,100)]):
            ccx=bar*0.6+i*bar*0.55; dw.ellipse((ccx-r,bar/2-r,ccx+r,bar/2+r),fill=col)
        ft=ImageFont.truetype("fredoka600.ttf",max(8,int(bar*0.5))); tw=dw.textlength("first_coffee.mp4",font=ft); dw.text((win.width/2-tw/2,bar*0.2),"first_coffee.mp4",font=ft,fill=(122,100,158))
    base.paste(content,(0,int(bar)))
    win=Image.new('RGBA',win.size,(0,0,0,0)); win.paste(base,(0,0),m)
    if sh>0.02:
        s=Image.new('RGBA',(W,H),(0,0,0,0)); ss=Image.new('RGBA',win.size,(0,0,0,int(150*sh))); s.paste(ss,(int(x0)+8,int(y0)+18),m)
        img=Image.alpha_composite(img,s.filter(ImageFilter.GaussianBlur(22)))
    img.alpha_composite(win,(int(x0),int(y0)))
    img.convert('RGB').save(f'tr/{k:03d}.png')
print(n)
