import io
from pathlib import Path
import streamlit as st
from PIL import Image, ImageDraw, ImageFont, ImageOps

st.set_page_config(page_title='trustedDialog Preview Builder', page_icon='✉️', layout='wide')
ROOT=Path(__file__).parent
REFERENCE=Image.open(ROOT/'gmx_ppt_reference.png').convert('RGBA')
TICK=Image.open(ROOT/'blue_tick.png').convert('RGBA')
# Reference is a direct crop of the rendered PowerPoint slide. Phone frame, GMX chrome,
# Otto Holler, GMX Magazin, Shopping World and bottom navigation are therefore already final pixels.
CROP_X,CROP_Y=718,48
PPI=120.0

def X(inches): return round(inches*PPI-CROP_X)
def Y(inches): return round(inches*PPI-CROP_Y)
def W(inches): return round(inches*PPI)
def H(inches): return round(inches*PPI)

def font(size,bold=False):
    # Roboto is the font used by the PPTX. Liberation Sans is only a fallback.
    candidates=[
      '/usr/share/fonts/truetype/roboto/unhinted/RobotoTTF/Roboto-Bold.ttf' if bold else '/usr/share/fonts/truetype/roboto/unhinted/RobotoTTF/Roboto-Regular.ttf',
      '/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf' if bold else '/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf'
    ]
    for p in candidates:
        try:return ImageFont.truetype(p,size)
        except OSError:pass
    return ImageFont.load_default()

def circle(im,size):
    im=ImageOps.fit(im.convert('RGBA'),(size,size),Image.Resampling.LANCZOS)
    m=Image.new('L',(size,size),0); ImageDraw.Draw(m).ellipse((0,0,size-1,size-1),fill=255); im.putalpha(m); return im

def fallback_avatar(name,color):
    s=''.join(w[0] for w in name.split()[:2] if w).upper() or 'M'
    im=Image.new('RGBA',(128,128),color); d=ImageDraw.Draw(im); f=font(42,True); b=d.textbbox((0,0),s,font=f)
    d.text(((128-(b[2]-b[0]))/2,(128-(b[3]-b[1]))/2-2),s,font=f,fill='white'); return im

def cover(im,size): return ImageOps.fit(im.convert('RGBA'),size,Image.Resampling.LANCZOS)

def build(sender,subject,preview,avatar,hero=None):
    im=REFERENCE.copy(); d=ImageDraw.Draw(im)
    # These boxes correspond to the editable PowerPoint objects only.
    # Nothing below the first trustedDialog mail is touched.
    # avatar
    avx,avy,avs=X(6.525),Y(2.280),W(.319)
    d.ellipse((avx-2,avy-2,avx+avs+2,avy+avs+2),fill='white')
    im.alpha_composite(circle(avatar,avs),(avx,avy))
    # sender line: clear Marke + old tick, but not time
    d.rectangle((X(6.81),Y(2.245),X(8.48),Y(2.525)),fill='white')
    f_sender=font(round(9/72*PPI),True)
    tx,ty=X(6.836),Y(2.285)
    d.text((tx,ty),sender,font=f_sender,fill='#111111')
    tick=TICK.resize((W(.138),W(.138)),Image.Resampling.LANCZOS)
    tick_x=min(round(tx+d.textlength(sender,font=f_sender)+5),X(8.45)); tick_y=Y(2.317)
    im.alpha_composite(tick,(tick_x,tick_y))
    # subject and preview exact 9pt Roboto
    d.rectangle((X(6.81),Y(2.435),X(9.19),Y(2.720)),fill='white')
    f=font(round(9/72*PPI),False)
    d.text((X(6.836),Y(2.475)),subject,font=f,fill='#111111')
    d.text((X(6.836),Y(2.672)),preview,font=f,fill='#aaaaaa')
    # uploaded preview image exactly replaces PPT rounded rectangle. When no upload exists,
    # the original magenta placeholder from PPT remains untouched.
    if hero is not None:
        ix,iy,iw,ih=X(6.931),Y(2.901),W(2.007),H(.854)
        art=cover(hero,(iw,ih)); mask=Image.new('L',(iw,ih),0); ImageDraw.Draw(mask).rounded_rectangle((0,0,iw-1,ih-1),radius=4,fill=255); art.putalpha(mask)
        im.alpha_composite(art,(ix,iy))
    return im

for k,v in {'sender':'Marke','subject':'Betreff','preview':'Preview','color':'#8EA8CE'}.items():st.session_state.setdefault(k,v)
st.title('trustedDialog Preview Builder')
st.caption('GMX Live-Vorschau direkt auf Basis der PowerPoint-Vorlage')
left,right=st.columns([.78,1.22],gap='large')
with left:
    st.subheader('Inhalte')
    st.text_input('Absender / Marke',key='sender',max_chars=29)
    st.text_input('Betreff',key='subject',max_chars=29)
    st.text_input('Preview-Text',key='preview',max_chars=29)
    st.color_picker('Fallback-Avatarfarbe',key='color')
    af=st.file_uploader('Avatar / Logo',type=['png','jpg','jpeg','webp'])
    hf=st.file_uploader('Preview-Bild 1088 × 464 px',type=['png','jpg','jpeg','webp'])
av=fallback_avatar(st.session_state.sender,st.session_state.color)
if af:
    try:av=Image.open(af).convert('RGBA')
    except Exception:pass
hero=None
if hf:
    try:hero=Image.open(hf).convert('RGBA')
    except Exception:pass
out=build(st.session_state.sender,st.session_state.subject,st.session_state.preview,av,hero)
with right:
    st.subheader('GMX Live-Vorschau')
    st.image(out,width=416)
    b=io.BytesIO();out.save(b,'PNG');st.download_button('Mockup als PNG herunterladen',b.getvalue(),'GMX_trustedDialog_Preview.png','image/png')
