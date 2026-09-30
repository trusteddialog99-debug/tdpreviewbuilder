import io
from pathlib import Path
import streamlit as st
from PIL import Image, ImageDraw, ImageFont, ImageOps

st.set_page_config(page_title='trustedDialog Preview Builder', page_icon='✉️', layout='wide')
ROOT=Path(__file__).parent
SCREEN=Image.open(ROOT/'gmx_screen.png').convert('RGBA')
FRAME=Image.open(ROOT/'iphone_frame.png').convert('RGBA')

# Exact PowerPoint overlay geometry, converted from slide coordinates to source-image pixels.
PIC_X, PIC_Y, PIC_W, PIC_H = 6.284, 0.633, 2.891, 6.255
SW, SH = SCREEN.size

def sx(v): return round((v-PIC_X)/PIC_W*SW)
def sy(v): return round((v-PIC_Y)/PIC_H*SH)
def sw(v): return round(v/PIC_W*SW)
def sh(v): return round(v/PIC_H*SH)

def get_font(size,bold=False):
    candidates=[
        '/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf' if bold else '/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf',
        '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf' if bold else '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
    ]
    for p in candidates:
        try:return ImageFont.truetype(p,size)
        except OSError:pass
    return ImageFont.load_default()

def cover(im,size): return ImageOps.fit(im.convert('RGBA'),size,Image.Resampling.LANCZOS)
def circle(im,size):
    im=cover(im,(size,size)); mask=Image.new('L',(size,size),0); ImageDraw.Draw(mask).ellipse((0,0,size-1,size-1),fill=255); im.putalpha(mask); return im

def fallback_avatar(name,color):
    im=Image.new('RGBA',(180,180),color); d=ImageDraw.Draw(im); text=''.join(w[0] for w in name.split()[:2] if w).upper() or 'M'; f=get_font(70,True); box=d.textbbox((0,0),text,font=f); d.text(((180-(box[2]-box[0]))/2,(180-(box[3]-box[1]))/2-4),text,font=f,fill='white'); return im

def placeholder():
    im=Image.new('RGBA',(1088,464),'#ff00e8'); d=ImageDraw.Draw(im); text='Bild einfügen'; f=get_font(62); box=d.textbbox((0,0),text,font=f); d.text(((1088-(box[2]-box[0]))/2,(464-(box[3]-box[1]))/2-4),text,font=f,fill='white'); return im

def text_at(draw,text,left,top,width,height,color,bold=False,align='left'):
    # PPT font sizes are converted proportionally into native screenshot pixels.
    px=max(12,round(height*0.72)); f=get_font(px,bold)
    box=draw.textbbox((0,0),text,font=f); tw=box[2]-box[0]; th=box[3]-box[1]
    x=left if align=='left' else left+width-tw
    y=top+(height-th)//2-1
    draw.text((x,y),text,font=f,fill=color)

def build_screen(sender,subject,preview,avatar,hero):
    # The native GMX screenshot remains intact, including all lower emails and bottom navigation.
    im=SCREEN.copy(); d=ImageDraw.Draw(im)

    # Clear only the PowerPoint-defined variable overlays, never the rest of the inbox.
    # first row text block
    clear_left=sx(6.80); clear_top=sy(2.24); clear_right=sx(9.18); clear_bottom=sy(3.02)
    d.rectangle((clear_left,clear_top,clear_right,clear_bottom),fill='white')
    # circle avatar region
    av_left,av_top,av_size=sx(6.525),sy(2.280),sw(0.319)
    d.ellipse((av_left-2,av_top-2,av_left+av_size+2,av_top+av_size+2),fill='white')
    # preview image region taken exactly from PPT rounded rectangle geometry
    img_left,img_top,img_w,img_h=sx(6.931),sy(2.901),sw(2.007),sh(0.854)
    d.rounded_rectangle((img_left-3,img_top-3,img_left+img_w+3,img_top+img_h+3),radius=8,fill='white')

    av=circle(avatar,av_size); im.alpha_composite(av,(av_left,av_top))

    sender_l,sender_t,sender_w,sender_h=sx(6.836),sy(2.259),sw(1.844),sh(0.252)
    text_at(d,sender,sender_l,sender_t,sender_w,sender_h,'#111111',True)
    # blue tick position from PPT image 31, immediately following the sender but capped in the original region
    sf=get_font(max(12,round(sender_h*0.72)),True); name_width=d.textlength(sender,font=sf)
    tick_size=sw(0.138); tick_x=min(sender_l+round(name_width)+8,sx(8.46)); tick_y=sy(2.317)
    d.ellipse((tick_x,tick_y,tick_x+tick_size,tick_y+tick_size),fill='#4b8dcb')
    tf=get_font(max(10,round(tick_size*.70)),True); d.text((tick_x+round(tick_size*.22),tick_y-round(tick_size*.10)),'✓',font=tf,fill='white')

    text_at(d,subject,sx(6.836),sy(2.449),sw(2.339),sh(0.252),'#111111')
    text_at(d,preview,sx(6.836),sy(2.646),sw(2.332),sh(0.252),'#aaaaaa')
    text_at(d,'09:33',sx(8.707),sy(2.276),sw(0.462),sh(0.219),'#999999',False,'right')

    image=cover(hero,(img_w,img_h)); mask=Image.new('L',(img_w,img_h),0); ImageDraw.Draw(mask).rounded_rectangle((0,0,img_w-1,img_h-1),radius=8,fill=255); image.putalpha(mask); im.alpha_composite(image,(img_left,img_top))
    return im

def with_frame(screen):
    # PPT geometry: screenshot picture 2 and iPhone frame picture 30 share the same slide coordinate system.
    # Reproduce their exact relative placement, then crop around the frame.
    scale=500
    min_x,min_y=6.02,0.42; max_x,max_y=9.46,7.15
    canvas=Image.new('RGBA',(round((max_x-min_x)*scale),round((max_y-min_y)*scale)),(0,0,0,0))
    # screenshot at exact PPT placement
    screen_size=(round(PIC_W*scale),round(PIC_H*scale)); scr=screen.resize(screen_size,Image.Resampling.LANCZOS)
    canvas.alpha_composite(scr,(round((PIC_X-min_x)*scale),round((PIC_Y-min_y)*scale)))
    # phone frame at exact PPT placement, transformed into an overlay by removing its white screen pixels
    fr=FRAME.resize((round(3.320*scale),round(6.609*scale)),Image.Resampling.LANCZOS)
    data=fr.getdata(); cleaned=[]
    for r,g,b,a in data:
        cleaned.append((r,g,b,0) if r>245 and g>245 and b>245 else (r,g,b,a))
    fr.putdata(cleaned)
    canvas.alpha_composite(fr,(round((6.069-min_x)*scale),round((0.468-min_y)*scale)))
    return canvas

for k,v in {'sender':'Marke','subject':'Betreff','preview':'Preview','color':'#8EA8CE'}.items():st.session_state.setdefault(k,v)
st.title('trustedDialog Preview Builder')
st.caption('GMX Mockup nach der gelieferten PowerPoint-Vorlage')
left,right=st.columns([0.75,1.25],gap='large')
with left:
    st.subheader('Inhalte')
    st.text_input('Absender / Marke',key='sender',max_chars=29)
    st.text_input('Betreff',key='subject',max_chars=29)
    st.text_input('Preview-Text',key='preview',max_chars=29)
    st.color_picker('Fallback-Avatarfarbe',key='color')
    avatar_file=st.file_uploader('Avatar / Logo',type=['png','jpg','jpeg','webp'])
    image_file=st.file_uploader('Preview-Bild 1088 × 464 px',type=['png','jpg','jpeg','webp'])
avatar=fallback_avatar(st.session_state.sender,st.session_state.color)
if avatar_file:
    try: avatar=Image.open(avatar_file).convert('RGBA')
    except Exception: pass
hero=placeholder()
if image_file:
    try: hero=Image.open(image_file).convert('RGBA')
    except Exception: pass
screen=build_screen(st.session_state.sender,st.session_state.subject,st.session_state.preview,avatar,hero)
phone=with_frame(screen)
with right:
    st.subheader('GMX Live-Vorschau')
    st.image(phone,width=420)
    buf=io.BytesIO(); phone.save(buf,'PNG')
    st.download_button('Mockup als PNG herunterladen',buf.getvalue(),'GMX_trustedDialog_Preview.png','image/png')
