from PIL import Image, ImageDraw, ImageFont
import numpy as np, math
af=ImageFont.truetype('anton.ttf',132)
LINES=["STAY WITH ME,","GETTING THERE","SOON"]
def strip(txt,stretch=1.5):
    d=ImageDraw.Draw(Image.new('L',(5,5))); w=int(d.textlength(txt,font=af))+10
    im=Image.new('L',(w,200),0); ImageDraw.Draw(im).text((0,10),txt,font=af,fill=255)
    bb=im.getbbox(); im=im.crop((0,bb[1],w,bb[3])); im=im.resize((im.width,int(im.height*stretch)),Image.LANCZOS)
    return np.array(im).astype(np.float32)/255
STR=[strip(t) for t in LINES]
def cylinder(rot,R=360,rowh=205):
    Wc=2*R; Hc=rowh*len(STR); circ=2*math.pi*R
    P=int(circ)
    out=np.zeros((Hc,Wc),np.float32)
    xs=np.arange(Wc)-R+0.5; th=np.arcsin(np.clip(xs/R,-0.999,0.999)); shade=np.cos(th)
    f=0.72+0.33*shade  # bulge
    for r,S in enumerate(STR):
        h,sw=S.shape
        pad=np.zeros((h,P),np.float32); pad[:,:min(sw,P)]=S[:,:min(sw,P)]
        u=((th-rot)/(2*math.pi)*circ)%P
        ui=u.astype(int)
        yy=np.arange(rowh)[:,None]-rowh/2
        sy=yy/f[None,:]+h/2
        valid=(sy>=0)&(sy<h-1)
        syi=np.clip(sy,0,h-1).astype(int)
        col=pad[syi,ui[None,:].repeat(rowh,0)]*valid
        out[r*rowh:(r+1)*rowh]=np.maximum(out[r*rowh:(r+1)*rowh],col*(0.3+0.7*shade)[None,:])
    return out
