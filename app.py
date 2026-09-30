import io
from pathlib import Path
import streamlit as st
from PIL import Image, ImageDraw, ImageFont, ImageOps

st.set_page_config(page_title='trustedDialog Preview Builder', page_icon='✉️', layout='wide')
ROOT=Path(__file__).parent
BASE=Image.open(ROOT/'gmx_ppt_reference.png').convert('RGBA')
TICK=Image.open(ROOT/'blue_tick.png').convert('RGBA')
CROP_X,CROP_Y=718,48
PPI=120.0

def X(i): return round(i*PPI-CROP_X)
def Y(i): return round(i*PPI-CROP_Y)
def W(i): return round(i*PPI)
def H(i): return round(i*PPI)

def font(pt,bold=False):
    px=round(pt/72*PPI)
    cand=['/usr/share/fonts/truetype/roboto/unhinted/RobotoTTF/Roboto-Bold.ttf' if bold else '/usr/share/fonts/truetype/roboto/unhinted/RobotoTTF/Roboto-Regular.ttf','/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf' if bold else '/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf']
    for p in cand:
        try:return ImageFont.truetype(p,px)
        except OSError:pass
    return ImageFont.load_default()

def ppt_text_xy(left,top):
    # PowerPoint text boxes have 0.10in left and 0.05in top inner margins.
    return X(left+0.10),Y(top+0.05)

def circle(im,size):
    im=ImageOps.fit(im.convert('RGBA'),(size,size),Image.Resampling.LANCZOS); m=Image.new('L',(size,size)); ImageDraw.Draw(m).ellipse((0,0,size-1,size-1),fill=255); im.putalpha(m); return im

def fallback(name,color):
    im=Image.new('RGBA',(160,160),color);d=ImageDraw.Draw(im);s=''.join(w[0] for w in name.split()[:2] if w).upper() or 'M';f=font(9,True);b=d.textbbox((0,0),s,font=f);d.text(((160-(b[2]-b[0]))/2,(160-(b[3]-b[1]))/2),s,font=f,fill='white');return im

def fit(im,size):return ImageOps.fit(im.convert('RGBA'),size,Image.Resampling.LANCZOS)

def build(sender,subject,preview,avatar,hero):
    im=BASE.copy();d=ImageDraw.Draw(im)
    # Exact editable regions from the PPT shape bounds. Keep timestamp and everything below untouched.
    d.rectangle((X(6.80),Y(2.24),X(8.58),Y(2.52)),fill='white')
    d.rectangle((X(6.80),Y(2.43),X(9.08),Y(2.70)),fill='white')
    d.rectangle((X(6.80),Y(2.63),X(9.08),Y(2.89)),fill='white')
    # avatar exact 0.3194in
    ax,ay,asz=X(6.5250),Y(2.2805),W(.3194)
    d.ellipse((ax-1,ay-1,ax+asz+1,ay+asz+1),fill='white');im.alpha_composite(circle(avatar,asz),(ax,ay))
    # text exact PowerPoint inner-margin origin and 9pt Roboto
    sx,sy=ppt_text_xy(6.8357,2.2594); fs=font(9,True);d.text((sx,sy),sender,font=fs,fill='#111')
    # original tick asset, exact PPT dimensions and vertical coordinate; horizontal follows text
    ts=W(.1378); tick=TICK.resize((ts,ts),Image.Resampling.LANCZOS); tx=min(round(sx+d.textlength(sender,font=fs)+3),X(8.50)); ty=Y(2.3167); im.alpha_composite(tick,(tx,ty))
    bx,by=ppt_text_xy(6.8357,2.4490); px,py=ppt_text_xy(6.8357,2.6456); f=font(9)
    d.text((bx,by),subject,font=f,fill='#111'); d.text((px,py),preview,font=f,fill='#a6a6a6')
    # Leave original PPT placeholder perfectly untouched until an image is uploaded.
    if hero is not None:
        ix,iy,iw,ih=X(6.9311),Y(2.9014),W(2.0069),H(.8542); art=fit(hero,(iw,ih));mask=Image.new('L',(iw,ih));ImageDraw.Draw(mask).rounded_rectangle((0,0,iw-1,ih-1),radius=4,fill=255);art.putalpha(mask);im.alpha_composite(art,(ix,iy))
    return im

for k,v in {'sender':'Marke','subject':'Betreff','preview':'Preview','color':'#8EA8CE'}.items(): st.session_state.setdefault(k,v)
st.title('trustedDialog Preview Builder');st.caption('GMX Live-Vorschau auf Basis der PowerPoint-Geometrie')
l,r=st.columns([.78,1.22],gap='large')
with l:
 st.subheader('Inhalte');st.text_input('Absender / Marke',key='sender',max_chars=29);st.text_input('Betreff',key='subject',max_chars=29);st.text_input('Preview-Text',key='preview',max_chars=29);st.color_picker('Fallback-Avatarfarbe',key='color');af=st.file_uploader('Avatar / Logo',type=['png','jpg','jpeg','webp']);hf=st.file_uploader('Preview-Bild 1088 × 464 px',type=['png','jpg','jpeg','webp'])
av=fallback(st.session_state.sender,st.session_state.color)
if af:
 try:av=Image.open(af).convert('RGBA')
 except:pass
hero=None
if hf:
 try:hero=Image.open(hf).convert('RGBA')
 except:pass
out=build(st.session_state.sender,st.session_state.subject,st.session_state.preview,av,hero)
with r:
 st.subheader('GMX Live-Vorschau');st.image(out,width=416);b=io.BytesIO();out.save(b,'PNG');st.download_button('Mockup als PNG herunterladen',b.getvalue(),'GMX_trustedDialog_Preview.png','image/png')
