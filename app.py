import io
from pathlib import Path
import streamlit as st
from PIL import Image, ImageDraw, ImageFont, ImageOps

st.set_page_config(page_title='trustedDialog Preview Builder - GMX', page_icon='✉️', layout='wide')
ROOT=Path(__file__).parent
BASE=Image.open(ROOT/'gmx_base_crop.png').convert('RGBA')
PHONE=Image.open(ROOT/'phone_frame.png').convert('RGBA')

def font(sz,bold=False):
    for p in ['/usr/share/fonts/truetype/arial/arialbd.ttf' if bold else '/usr/share/fonts/truetype/arial/arial.ttf','/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf' if bold else '/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf']:
        try:return ImageFont.truetype(p,sz)
        except:pass
    return ImageFont.load_default()

def fit(im,size): return ImageOps.fit(im.convert('RGBA'),size,Image.Resampling.LANCZOS)
def circle(im,size):
    im=fit(im,(size,size)); m=Image.new('L',(size,size)); ImageDraw.Draw(m).ellipse((0,0,size-1,size-1),fill=255); im.putalpha(m); return im

def initials(name,color='#8EA8CE'):
    im=Image.new('RGBA',(120,120),color); d=ImageDraw.Draw(im); s=''.join(x[0] for x in name.split()[:2] if x).upper() or 'M'; f=font(48,True); b=d.textbbox((0,0),s,font=f); d.text(((120-(b[2]-b[0]))/2,(120-(b[3]-b[1]))/2-3),s,font=f,fill='white'); return im

def build(sender,subject,preview,avatar,hero):
    # BASE is cropped directly from the PPT screenshot. Only the variable overlay elements are redrawn.
    im=BASE.copy(); d=ImageDraw.Draw(im)
    # map PPT overlay coordinates into crop pixels
    # clear variable first-mail area only; native header/nav and subsequent rows remain original screenshot pixels
    d.rectangle((0,0,902,510),fill='white')
    # retain top header/search from original base
    im.alpha_composite(BASE.crop((0,0,902,235)),(0,0))
    # separator and status strip reproduced from screenshot crop
    d.line((0,235,902,235),fill='#d8d8d8',width=2)
    d.text((20,250),'•••',font=font(22,True),fill='#4aa7df'); d.text((112,254),'E-Mails empfangen',font=font(18),fill='#777777')
    d.line((0,294,902,294),fill='#d8d8d8',width=2)
    av=circle(avatar,72); im.alpha_composite(av,(10,315))
    d.text((105,314),sender,font=font(27,True),fill='#111111')
    sx=105+int(d.textlength(sender,font=font(27,True)))+9; d.ellipse((sx,320,sx+25,345),fill='#4E8DCA'); d.text((sx+5,316),'✓',font=font(18,True),fill='white')
    d.text((760,320),'09:33',font=font(20),fill='#999999')
    d.text((105,354),subject,font=font(25),fill='#111111')
    d.text((105,395),preview,font=font(24),fill='#AAAAAA')
    art=fit(hero,(663,285)); im.alpha_composite(art,(119,438))
    return im

def phone_comp(inbox):
    # The PPT phone frame is a standalone transparent device frame. Place the exact GMX inbox inside it.
    frame=PHONE.copy()
    # screen interior estimated directly from embedded frame asset; small insets preserve black bezel / Dynamic Island.
    screen=fit(inbox,(1040,2240))
    # resize inbox preserving the full composition; source PPT frame is intentionally the authoritative outer frame.
    frame.alpha_composite(screen,(112,124))
    # overlay frame again if alpha identifies transparent screen; use dark-border pixels from original
    return frame

for k,v in {'sender':'Marke','subject':'Betreff','preview':'Preview','color':'#8EA8CE'}.items(): st.session_state.setdefault(k,v)

st.title('trustedDialog Preview Builder')
st.caption('GMX Mockup, aufgebaut auf der gelieferten PowerPoint-Vorlage.')
left,right=st.columns([0.72,1.28],gap='large')
with left:
    st.subheader('Inhalte')
    st.text_input('Absender / Marke',key='sender',max_chars=29)
    st.text_input('Betreff',key='subject',max_chars=29)
    st.text_input('Preview-Text',key='preview',max_chars=29)
    st.color_picker('Fallback-Avatarfarbe',key='color')
    au=st.file_uploader('Avatar / Logo',type=['png','jpg','jpeg','webp'])
    hu=st.file_uploader('Preview-Bild 1088 × 464 px',type=['png','jpg','jpeg','webp'])
avatar=initials(st.session_state.sender,st.session_state.color)
if au:
    try:avatar=Image.open(au).convert('RGBA')
    except:pass
if hu:
    try:hero=Image.open(hu).convert('RGBA')
    except:hero=Image.new('RGBA',(1088,464),'#ff00e8')
else:
    hero=Image.new('RGBA',(1088,464),'#ff00e8'); dd=ImageDraw.Draw(hero); f=font(64); t='Bild einfügen'; b=dd.textbbox((0,0),t,font=f); dd.text(((1088-(b[2]-b[0]))/2,(464-(b[3]-b[1]))/2),t,font=f,fill='white')
inbox=build(st.session_state.sender,st.session_state.subject,st.session_state.preview,avatar,hero)
phone=phone_comp(inbox)
with right:
    st.subheader('GMX Live-Vorschau')
    mode=st.radio('Ansicht',['Mit Phone-Frame','Postfach pur'],horizontal=True)
    current=phone if mode=='Mit Phone-Frame' else inbox
    st.image(current,width=430)
    buf=io.BytesIO(); current.save(buf,'PNG')
    st.download_button('Mockup als PNG herunterladen',buf.getvalue(),'GMX_trustedDialog_Preview.png','image/png')
st.caption('Die statischen GMX-UI-Bereiche stammen aus der bereitgestellten PPTX-Vorlage; dynamisch ausgetauscht werden die kundenbezogenen Preview-Inhalte.')
