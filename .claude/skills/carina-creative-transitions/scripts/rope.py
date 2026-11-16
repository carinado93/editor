import sys; sys.path.insert(0,'.')
from descend import *
import descend as D
from maskfix import mask_fixed
L=34; CLICK=16
STKF={'Z':60,'P':276,'Y':402}; XS={'Z':520,'P':960,'Y':1400}
def rope_y(x): return 70+80*(1-((x-960)/1000)**2)
def cutout(i,k):
    fr=frame(i); m=mask_fixed(i,fr,k=='Z')
    rgba=np.dstack([fr,m*255]).astype(np.uint8); im=Image.fromarray(rgba,'RGBA'); return im.crop(im.getbbox())
def sticker(k,box=300):
    im=cutout(STKF[k],k); sc=box/max(im.width,im.height); im=im.resize((int(im.width*sc),int(im.height*sc)),Image.LANCZOS)
    pad=22; c=Image.new('RGBA',(im.width+2*pad,im.height+2*pad),(0,0,0,0)); c.paste(im,(pad,pad),im)
    a=c.getchannel('A').filter(ImageFilter.MaxFilter(17)).filter(ImageFilter.GaussianBlur(1.2))
    wh=Image.new('RGBA',c.size,(255,255,255,255)); wh.putalpha(a)
    sh=Image.new('RGBA',c.size,(0,0,0,0)); sh.putalpha(a.point(lambda v:int(v*0.45))); sh=sh.filter(ImageFilter.GaussianBlur(8))
    o=Image.new('RGBA',(c.width+20,c.height+20),(0,0,0,0)); o.alpha_composite(sh,(10,16)); o.alpha_composite(wh); o.alpha_composite(c); return o
STK={k:sticker(k) for k in SH}
pin=Image.new('RGBA',(22,48),(0,0,0,0)); dp=ImageDraw.Draw(pin)
dp.rounded_rectangle((2,0,20,46),5,fill=(196,150,104,255),outline=(120,84,54,255),width=2); dp.line((11,6,11,40),fill=(150,108,70,255),width=2)
def cursor_img(s=1.0):
    pts=[(0,0),(0,34),(9,26),(15,40),(21,37),(15,24),(27,24)]
    im=Image.new('RGBA',(70,90),(0,0,0,0)); d=ImageDraw.Draw(im)
    d.polygon([(x*2+4,y*2+4) for x,y in pts],fill=(255,255,255,255),outline=(0,0,0,255),width=4)
    return im if s==1 else im.resize((int(70*s),int(90*s)),Image.LANCZOS)
def rot_paste(img,st,x,yt,ang,alpha=1.0,scale=1.0):
    im=st if scale==1 else st.resize((max(1,int(st.width*scale)),max(1,int(st.height*scale))),Image.LANCZOS)
    if alpha<1: im=im.copy(); im.putalpha(im.getchannel('A').point(lambda v:int(v*alpha)))
    S_=max(im.width,im.height)*2+40; big=Image.new('RGBA',(S_,S_),(0,0,0,0)); c=S_//2
    big.alpha_composite(im,(c-im.width//2,c-6)); big=big.rotate(ang,resample=Image.BICUBIC,center=(c,c))
    img.alpha_composite(big,(int(x-c),int(yt-c)))
KEYS=list(SH)
def render(i):
    k=None
    for kk,(a,_,_) in SH.items():
        if a<=i<a+L: k=kk
    if k is None:
        base=frame(i); img=Image.fromarray(base.astype(np.uint8)).convert('RGBA')
    else:
        a=SH[k][0]; j=i-a; pl=plates[k]; fr=frame(i)
        q=a+L-6; mq=mask_fixed(q,frame(q),k=='Z'); ys,xs=np.nonzero(mq>0.5)
        bx0,bx1,by0,by1=xs.min(),xs.max(),ys.min(),ys.max()
        base=pl.copy(); w=0
        if j>=L-7:
            m=mask_fixed(i,fr,k=='Z'); w=eo((j-(L-7))/6)
            live=pl*(1-m[...,None])+fr*m[...,None]
            base=base*(1-w)+live*w
            if j>=L-2: base=base*0.5+fr*0.5 if j==L-2 else fr
        dim=0.28*(1-eo((j-CLICK)/10)) if j>=CLICK else 0.28*eo(j/6)
        base=base*(1-dim)
        img=Image.fromarray(np.clip(base,0,255).astype(np.uint8)).convert('RGBA'); d=ImageDraw.Draw(img)
        # rope
        ro=0 if j<CLICK+4 else eo((j-CLICK-4)/9)   # rope leaves upward
        oy=-260*ro
        rp=eo(j/7); xe=-20+1960*rp
        pts=[(x,rope_y(x)+oy) for x in np.linspace(-20,xe,80)]
        d.line(pts,fill=(70,55,45,255),width=5); d.line([(x,y-1) for x,y in pts],fill=(150,128,108,255),width=2)
        for n,kk in enumerate(KEYS):
            x=XS[kk]; td=2+2*n
            if j<td: continue
            dt=(j-td)/30; drop=eo(dt/0.25); py=rope_y(x)+oy
            ang=14*math.exp(-dt*1.6)*math.sin(dt*7+n)+2.2*math.sin(i/30*2.2+n*1.3)
            used=KEYS.index(kk)<KEYS.index(k)
            if kk==k and j>=CLICK:
                # fly to her
                t=(j-CLICK)/(L-3-CLICK); e=eo(min(t,1))
                st=STK[kk]; sf=((bx1-bx0)/(st.width-64) if st.width>st.height else (by1-by0)/(st.height-64))*1.03; s=1+(sf-1)*e
                sx,sy=x,py-6+st.height/2; tx,ty=(bx0+bx1)/2,by1-(st.height-64)*sf/2
                cx=sx+(tx-sx)*e; cy=sy+(ty-sy)*e-160*math.sin(math.pi*e)
                al=1-w
                if al>0.02: rot_paste(img,st,cx,cy-st.height*s/2+6*s,ang*(1-e),al,s)
                continue
            yy=py-(1-drop)*300
            rot_paste(img,STK[kk],x,yy,ang,0.45 if used else 1.0)
            img.alpha_composite(pin,(int(x-11),int(yy-28)))
            if used:
                d2=ImageDraw.Draw(img); cx_,cy_=x+70,yy+40
                d2.ellipse([cx_-26,cy_-26,cx_+26,cy_+26],fill=LILAC); d2.line([(cx_-12,cy_),(cx_-3,cy_+10),(cx_+14,cy_-10)],fill=WHITE,width=6)
        # click ring + cursor
        tgt=(XS[k]+10,rope_y(XS[k])+120+oy)
        if CLICK<=j<CLICK+12:
            kq=(j-CLICK)/12; r=int(40+220*kq)
            ring=Image.new('RGBA',(W,H),(0,0,0,0)); ImageDraw.Draw(ring).ellipse((tgt[0]-r,tgt[1]-r,tgt[0]+r,tgt[1]+r),outline=(255,255,255,int(255*(1-kq))),width=6)
            img.alpha_composite(ring)
        if 7<=j<CLICK+6:
            p=eo((j-7)/(CLICK-8)); sx,sy=1650,1000
            cxp=sx+(tgt[0]-sx)*p; cyp=sy+(tgt[1]-sy)*p
            img.alpha_composite(cursor_img(0.82 if CLICK-1<=j<=CLICK+1 else 1),(int(cxp),int(cyp)))
    # pill (pops at click)
    for kk in KEYS:
        a=SH[kk][0]; land=a+CLICK+1; n=KEYS.index(kk)+1; end=SH[KEYS[n]][0]+CLICK+1 if n<3 else 10**9
        if land<=i<end+8: pill_at(img,kk,i-land,(i-end) if i>=end else -1)
    if i<=30: title(img,int(i*52/30))
    img.convert('RGB').save(f'outB/{i:04d}.png')
def pill_at(img,k,j,jo):
    a,name,mins=SH[k]; sc=eob(j/9); out=0 if jo<0 else eo(jo/8)
    f1=fnt('titan.ttf',64); f2=fnt('fredoka700.ttf',52)
    tw=f1.getlength(name); mw=f2.getlength('× '+mins); pw=int(110+tw+30+mw+50); ph=110
    p=Image.new('RGBA',(pw+20,ph+20),(0,0,0,0)); d=ImageDraw.Draw(p)
    d.rounded_rectangle([10,14,pw+10,ph+14],ph//2,fill=(90,70,125,90)); d.rounded_rectangle([10,10,pw+10,ph+10],ph//2,fill=LILAC+(255,))
    stopwatch(d,72,10+ph//2+6,26,j*0.35,WHITE); d.text((120,10+ph//2),name,font=f1,fill=WHITE,anchor='lm')
    d.rounded_rectangle([120+tw+20,30,120+tw+20+mw+30,ph-10],30,fill=WHITE); d.text((120+tw+35,10+ph//2+2),'× '+mins,font=f2,fill=LILD,anchor='lm')
    s=max(sc,0.01)*(1-0.3*out); p=p.resize((max(1,int(p.width*s)),max(1,int(p.height*s))),Image.LANCZOS)
    if out>0: p.putalpha(p.getchannel('A').point(lambda v:int(v*(1-out))))
    img.alpha_composite(p,(80,int(70-120*out)))
lo,hi=int(sys.argv[1]),int(sys.argv[2])
for i in range(lo,hi): render(i)
