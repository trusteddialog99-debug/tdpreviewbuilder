import io
from pathlib import Path
import streamlit as st
from PIL import Image, ImageDraw, ImageFont, ImageOps

st.set_page_config(page_title='trustedDialog Preview Builder', page_icon='✉️', layout='wide')
ROOT=Path(__file__).parent
REF=Image.open(ROOT/'gmx_reference.png').convert('RGBA')
FRAME=Image.open(ROOT/'phone_frame.png').convert('RGBA')

def font(sz,bold=False):
    for p in ['/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf' if bold else '/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf','/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf' if bold else '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf']:
        try:return ImageFont.truetype(p,sz)
        except OSError:pass
    return ImageFont.load_default()

def fit(im,size): return ImageOps.fit(im.convert('RGBA'),size,Image.Resampling.LANCZOS)
def round_im(im,size):
    im=fit(im,(size,size)); m=Image.new('L',(size,size)); ImageDraw.Draw(m).ellipse((0,0,size-1,size-1),fill=255); im.putalpha(m); return im

def avatar_fallback(name,color):
    im=Image.new('RGBA',(140,140),color); d=ImageDraw.Draw(im); s=''.join(w[0] for w in name.split()[:2] if w).upper() or 'M'; f=font(51,True); b=d.textbbox((0,0),s,font=f); d.text(((140-(b[2]-b[0]))/2,(140-(b[3]-b[1]))/2-3),s,font=f,fill='white'); return im

def pink_placeholder():
    im=Image.new('RGBA',(1088,464),'#ff00e8');d=ImageDraw.Draw(im); t='Bild einfügen';f=font(64);b=d.textbbox((0,0),t,font=f);d.text(((1088-(b[2]-b[0]))/2,(464-(b[3]-b[1]))/2-5),t,font=f,fill='white');return im

def build_screen(sender,subject,preview,avatar,hero):
    # Start with the actual GMX mobile screenshot embedded in the PPTX.
    im=REF.copy(); d=ImageDraw.Draw(im)
    # Coordinates are in the native 954x2064 screenshot. Only customer-variable first-mail elements are covered.
    # Repaint first row's editable region while leaving GMX chrome and all lower rows untouched.
    d.rectangle((86,542,900,1195),fill='white')
    # subtle left margin and divider copied from reference appearance
    d.line((89,1194,895,1194),fill='#dedede',width=2)
    av=round_im(avatar,78); im.alpha_composite(av,(94,564))
    x=195
    d.text((x,563),sender,font=font(27,True),fill='#111111')
    sx=x+int(d.textlength(sender,font=font(27,True)))+10
    d.ellipse((sx,570,sx+25,595),fill='#4b8ccc');d.text((sx+5,566),'✓',font=font(18,True),fill='white')
    d.text((812,572),'09:33',font=font(19),fill='#969696')
    d.text((x,607),subject,font=font(25),fill='#111111')
    d.text((x,652),preview,font=font(24),fill='#aaaaaa')
    art=fit(hero,(700,299)); im.alpha_composite(art,(195,704))
    return im

def add_phone(screen):
    # Use the PPTX phone artwork only as an overlay around the GMX screenshot.
    # Fit screen to the visible inner display, then composite frame on top.
    canvas=Image.new('RGBA',FRAME.size,(255,255,255,0))
    display=fit(screen,(1034,2195)); canvas.alpha_composite(display,(116,137))
    # Keep only dark/opaque frame pixels, making its white interior transparent.
    fr=FRAME.copy(); px=fr.load()
    for y in range(fr.height):
        for x in range(fr.width):
            r,g,b,a=px[x,y]
            if r>238 and g>238 and b>238: px[x,y]=(r,g,b,0)
    canvas.alpha_composite(fr,(0,0)); return canvas

for k,v in {'sender':'Marke','subject':'Betreff','preview':'Preview','color':'#8EA8CE'}.items():st.session_state.setdefault(k,v)
st.title('trustedDialog Preview Builder')
st.caption('GMX Mobile Mockup auf Basis der PowerPoint-Referenz')
left,right=st.columns([0.72,1.28],gap='large')
with left:
    st.subheader('Inhalte')
    st.text_input('Absender / Marke',key='sender',max_chars=29)
    st.text_input('Betreff',key='subject',max_chars=29)
    st.text_input('Preview-Text',key='preview',max_chars=29)
    st.color_picker('Fallback-Avatarfarbe',key='color')
    au=st.file_uploader('Avatar / Logo',type=['png','jpg','jpeg','webp'])
    hu=st.file_uploader('Preview-Bild 1088 × 464 px',type=['png','jpg','jpeg','webp'])
av=avatar_fallback(st.session_state.sender,st.session_state.color)
if au:
    try:av=Image.open(au).convert('RGBA')
    except:pass
hero=pink_placeholder()
if hu:
    try:hero=Image.open(hu).convert('RGBA')
    except:pass
screen=build_screen(st.session_state.sender,st.session_state.subject,st.session_state.preview,av,hero)
phone=add_phone(screen)
with right:
    st.subheader('GMX Live-Vorschau')
    mode=st.radio('Ansicht',['Mit Phone-Frame','Postfach pur'],horizontal=True)
    out=phone if mode=='Mit Phone-Frame' else screen
    st.image(out,width=430)
    b=io.BytesIO();out.save(b,'PNG');st.download_button('Mockup als PNG herunterladen',b.getvalue(),'GMX_trustedDialog_Preview.png','image/png')
