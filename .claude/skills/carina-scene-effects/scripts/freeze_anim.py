from PIL import Image, ImageDraw, ImageFont, ImageFilter
import os
W,H=1920,1080; LILAC=(201,179,236); WHITE=(255,255,255)
bg=Image.open('freeze.png').convert('RGBA')
mask=Image.open('mask.png').convert('L').filter(ImageFilter.GaussianBlur(1.2))
person=bg.copy(); person.putalpha(mask)
f=ImageFont.truetype('titan.ttf',150); f2=ImageFont.truetype('fredoka700.ttf',76)
d0=ImageDraw.Draw(bg)
def word_layer(words_pos, font, shadow):
    L=Image.new('RGBA',(W,H),(0,0,0,0)); S=Image.new('RGBA',(W,H),(0,0,0,0))
    d=ImageDraw.Draw(L); ds=ImageDraw.Draw(S)
    for t,x,y,col in words_pos:
        ds.text((x+6,y+8),t,font=font,fill=shadow); d.text((x,y),t,font=font,fill=col)
    return Image.alpha_composite(S.filter(ImageFilter.GaussianBlur(10)),L)
# behind words positions: "A DAY" ends at 748, "IN MY LIFE" starts at 868
bl=d0.textbbox((0,0),'A DAY',font=f); br=d0.textbbox((0,0),'IN MY LIFE',font=f)
y=255-(bl[3]-bl[1])/2-bl[1]
xl=690-bl[2]; xr=858-br[0]
def xoff(full,prefix,font): return d0.textlength(prefix,font=font) if prefix else 0
behind=[('A',xl),('DAY',xl+xoff('A DAY','A ',f)),('IN',xr),('MY',xr+xoff('','IN ',f)),('LIFE',xr+xoff('','IN MY ',f))]
# front lines
l1='self-employed, self-doubting,'; l2='not giving up edition'
b1=d0.textbbox((0,0),l1,font=f2); b2=d0.textbbox((0,0),l2,font=f2)
x1=(W-(b1[2]-b1[0]))/2-b1[0]; x2=(W-(b2[2]-b2[0]))/2-b2[0]; y1=560; y2=645
front=[[(l1.split(' ')[0],x1,y1,WHITE)],[(l1.split(' ')[1],x1+d0.textlength(l1.split(' ')[0]+' ',font=f2),y1,WHITE)],[(l2,x2,y2,LILAC)]]
# timeline within 1s freeze @30fps: word i appears at frame
events=[(0,'b',0),(4,'b',1),(8,'b',2),(12,'b',3),(16,'b',4),(24,'f',0),(29,'f',1),(35,'f',2)]
os.makedirs('fz',exist_ok=True)
for fr in range(60):
    bw=[behind[i] for t,k,i in events if k=='b' and t<=fr]
    fw=[w for t,k,i in events if k=='f' and t<=fr for w in front[i]]
    img=bg
    if bw: img=Image.alpha_composite(img,word_layer([(t,x,y,LILAC) for t,x in bw],f,(40,25,70,200)))
    img=Image.alpha_composite(img,person)
    if fw: img=Image.alpha_composite(img,word_layer(fw,f2,(0,0,0,190)))
    img.convert('RGB').save(f'fz/{fr:03d}.png')
