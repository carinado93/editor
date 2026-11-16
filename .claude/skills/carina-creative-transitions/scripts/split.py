from PIL import Image, ImageDraw, ImageFilter
import os, glob
W,H=1920,1080; LIL=(214,198,240)
def ease(x): x=max(0,min(1,x)); return 1-(1-x)**3
def back(x): x=max(0,min(1,x)); c=1.5; return max(0.01,1+(c+1)*(x-1)**3+c*(x-1)**2)
def lerp(a,b,p): return a+(b-a)*p
cf=sorted(glob.glob('cf/*.png')); bf=sorted(glob.glob('bf/*.png'))
os.makedirs('sp',exist_ok=True); [os.remove(f) for f in glob.glob('sp/*')]
def card(img,src,cx,cy,w,rad,shadow=True):
    w=int(w); h=int(w*9/16); x0=int(cx-w/2); y0=int(cy-h/2)
    if shadow:
        s=Image.new('RGBA',(W,H),(0,0,0,0)); ImageDraw.Draw(s).rounded_rectangle((x0+10,y0+22,x0+w+10,y0+h+22),int(rad),fill=(60,30,90,90))
        img.alpha_composite(s.filter(ImageFilter.GaussianBlur(24)))
    m=Image.new('L',(w,h),0); ImageDraw.Draw(m).rounded_rectangle((0,0,w-1,h-1),int(rad),fill=255)
    img.paste(Image.open(src).convert('RGB').resize((w,h),Image.LANCZOS),(x0,y0),m)
SPD=1.5; C0=35; NC=int((len(cf)-1-C0)/SPD)   # coffee frames shown
MOVE=10; MAXI=10
n=0
total=len(bf)
for j in range(total):
    img=Image.new('RGBA',(W,H),LIL+(255,))
    ci=min(len(cf)-1,int(C0+j*SPD))
    if j<NC:
        p=ease(j/MOVE); 
        card(img,cf[ci],lerp(580,490,p),lerp(540,560,p),lerp(1040,880,p),36)
        b=back(j/12); card(img,bf[j],1430,560,880*b,36)
    else:
        q=ease((j-NC)/MAXI)
        # coffee slides out left & fades
        if q<1:
            card(img,cf[-1],lerp(490,-500,q),560,880,36)
        card(img,bf[j],lerp(1430,960,q),lerp(560,540,q),lerp(880,1920,q),36*(1-q),shadow=q<0.95)
    img.convert('RGB').save(f'sp/{n:04d}.png'); n+=1
print(n,NC)
