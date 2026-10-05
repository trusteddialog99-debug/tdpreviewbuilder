import base64, html, json, io, re, socket, ipaddress
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen
import requests
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageColor
import streamlit as st
import streamlit.components.v1 as components
st.set_page_config(page_title='trustedDialog Preview Builder',page_icon='✉️',layout='wide')
SEAL_URL='https://img.ui-portal.de/trusteddialog/trustlogo/trusted-sign_GMX.svg'
GMX_LOGO_URL='https://logo.ui-portal.de/td/ab166bef-b456-4e67-984f-72fb64d4a2c6/bo10.svg'
@st.cache_data(show_spinner=False)
def remote_data_uri(url):
 try:
  req=Request(url,headers={'User-Agent':'Mozilla/5.0'})
  with urlopen(req,timeout=8) as response:
   data=response.read()
   content_type=response.headers.get_content_type() or 'image/svg+xml'
  return f'data:{content_type};base64,'+base64.b64encode(data).decode()
 except Exception:
  return url
SEAL=remote_data_uri(SEAL_URL)
GMX_LOGO=remote_data_uri(GMX_LOGO_URL)
def uri(f):
 if not f:return ''
 mime='image/svg+xml' if f.name.lower().endswith('.svg') else (f.type or 'image/png')
 return f'data:{mime};base64,'+base64.b64encode(f.getvalue()).decode()
def e(x):return html.escape(x or '',quote=True)
def display_text(x):
 return e(x[:34]+'...' if len(x)>34 else x)

UA='Mozilla/5.0 (compatible; trustedDialog-Preview-Builder/1.0)'
PREVIEW_SIZE=(1088,464)

def normalize_domain(value):
 value=(value or '').strip()
 if value and not value.startswith(('http://','https://')): value='https://'+value
 return value

def public_url(value):
 try:
  parsed=urlparse(value)
  if parsed.scheme not in ('http','https') or not parsed.hostname:return False
  for answer in socket.getaddrinfo(parsed.hostname,parsed.port or 443,type=socket.SOCK_STREAM):
   ip=ipaddress.ip_address(answer[4][0])
   if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:return False
  return True
 except Exception:return False

def safe_fetch(value,max_bytes=7000000):
 if not public_url(value):raise ValueError('Die Domain ist nicht öffentlich erreichbar oder wurde aus Sicherheitsgründen blockiert.')
 with requests.get(value,headers={'User-Agent':UA},timeout=12,stream=True,allow_redirects=True) as response:
  response.raise_for_status()
  if not public_url(response.url):raise ValueError('Die Weiterleitung wurde blockiert.')
  data=bytearray()
  for chunk in response.iter_content(65536):
   data.extend(chunk)
   if len(data)>max_bytes:raise ValueError('Die abgerufene Datei ist zu groß.')
  return bytes(data),response.url,response.headers.get('content-type','')

def meta(soup,*keys):
 for key in keys:
  node=soup.find('meta',attrs={'property':key}) or soup.find('meta',attrs={'name':key})
  if node and node.get('content'):return node['content'].strip()
 return ''

def unique(values):
 out=[];seen=set()
 for value in values:
  if value and value not in seen:seen.add(value);out.append(value)
 return out

def short(value,limit=37):
 value=re.sub(r'\s+',' ',value or '').strip()
 return value if len(value)<=limit else value[:limit-3].rstrip()+'...'

def analyze_site(value):
 raw,final_url,content_type=safe_fetch(normalize_domain(value),3000000)
 soup=BeautifulSoup(raw,'html.parser')
 title=meta(soup,'og:site_name') or (soup.title.get_text(' ',strip=True) if soup.title else '')
 host=(urlparse(final_url).hostname or '').replace('www.','')
 brand=re.split(r'\s*[|–—]\s*',title)[0].strip() if title else host.split('.')[0]
 brand=re.sub(r'\s+-\s+.*$','',brand).strip() or host
 description=meta(soup,'og:description','description')
 body_text=' '.join(soup.stripped_strings)
 offers=[]
 patterns=[r'\b\d{1,2}\s?%\s*(?:Rabatt|sparen|off)?\b',r'\b\d+(?:[,.]\d{1,2})?\s?€\s*(?:Rabatt|Gutschein|sparen)?\b',r'\b(?:Willkommensrabatt|Gratis Versand|kostenloser Versand|Sale|Gutschein|Rabatt)\b[^.!?]{0,65}']
 for pattern in patterns:offers.extend(re.findall(pattern,body_text,flags=re.I))
 offers=unique([re.sub(r'\s+',' ',x).strip(' -|') for x in offers])[:8]
 theme=meta(soup,'theme-color')
 colors=[]
 if theme:colors.append(theme)
 for source in [str(soup)[:350000]]:
  colors.extend(re.findall(r'#[0-9a-fA-F]{6}\b',source))
 colors=unique(colors)[:12]
 images=[];logos=[]
 og=meta(soup,'og:image','twitter:image')
 if og:images.append(urljoin(final_url,og))
 for tag in soup.find_all('img'):
  src=tag.get('src') or tag.get('data-src') or tag.get('data-lazy-src')
  if not src:continue
  src=urljoin(final_url,src)
  marker=(' '.join(tag.get('class',[]))+' '+tag.get('id','')+' '+tag.get('alt','')).lower()
  if 'logo' in marker:logos.append(src)
  elif not src.lower().split('?')[0].endswith(('.svg','.gif')):
   score=0
   if any(word in marker for word in ('hero','banner','stage','campaign','teaser')):score+=5
   try:
    width=int(str(tag.get('width','0')).replace('px',''));height=int(str(tag.get('height','0')).replace('px',''))
    if width>=600:score+=3
    if width and height and width/height>1.5:score+=2
   except Exception:pass
   images.append((score,src))
 for link in soup.find_all('link'):
  rel=' '.join(link.get('rel',[])).lower()
  if any(x in rel for x in ('icon','apple-touch-icon')) and link.get('href'):logos.append(urljoin(final_url,link['href']))
 images=unique([x[1] for x in sorted(images,key=lambda item:item[0],reverse=True)])[:10]
 logos=unique(logos)[:8]
 offer=offers[0] if offers else ''
 if offer:
  subject=short(('Jetzt '+offer+' sichern') if len(offer)<26 else offer)
  preheader=short('Angebot jetzt entdecken')
 else:
  subject=short('Neuigkeiten von '+brand)
  preheader=short('Jetzt Vorteile entdecken')
 return {'url':final_url,'brand':short(brand),'description':description,'offers':offers,'colors':colors,'images':images,'logos':logos,'subject':subject,'preheader':preheader}

def image_from_url(value):
 raw,_,_=safe_fetch(value,9000000)
 image=Image.open(io.BytesIO(raw));image.load();return image.convert('RGB')

def font(size,bold=False):
 paths=['/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf' if bold else '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf','/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf' if bold else '/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf']
 for path in paths:
  try:return ImageFont.truetype(path,size)
  except OSError:pass
 return ImageFont.load_default()

def readable_color(rgb):
 # Returns black or white according to WCAG-style relative luminance.
 r,g,b=[value/255 for value in rgb]
 lum=.2126*r+.7152*g+.0722*b
 return '#111111' if lum>.56 else '#ffffff'

def safe_brand_rgb(value):
 try:
  rgb=ImageColor.getrgb(value)
  if len(rgb)==4:rgb=rgb[:3]
  return rgb
 except Exception:return (19,117,215)

def campaign_message(headline):
 """Reduce website wording to one dominant message and one short CTA."""
 text=re.sub(r'\s+',' ',headline or '').strip()
 percent=re.search(r'(?<!\d)(\d{1,2})\s?%',text)
 euro=re.search(r'(?<!\d)(\d+(?:[,.]\d{1,2})?)\s?€',text)
 urgent=next((word for word in ('Nur heute','Letzte Chance','Endet morgen') if word.lower() in text.lower()),'')
 if percent:
  value=percent.group(1)+' %'
  return urgent.upper() if urgent else 'BIS ZU',value,'SPAREN','JETZT SHOPPEN'
 if euro:
  value=euro.group(1)+' €'
  return urgent.upper() if urgent else 'JETZT',value,'SPAREN','ANGEBOT SICHERN'
 cleaned=re.sub(r'\b(jetzt|entdecken|sichern|shoppen|kaufen|angebot)\b','',text,flags=re.I)
 cleaned=re.sub(r'\s+',' ',cleaned).strip(' -–—!')
 words=cleaned.split()
 dominant=' '.join(words[:4]).upper() if words else 'NEU ENTDECKEN'
 return '',dominant,'','JETZT ENTDECKEN'

def fit_font(draw,text,max_width,start_size,min_size=25,bold=True):
 size=start_size
 while size>=min_size:
  candidate=font(size,bold)
  if draw.textlength(text,font=candidate)<=max_width:return candidate
  size-=2
 return font(min_size,bold)

def generate_preview(source,headline,brand_color='#1375d7'):
 """Create a compact, high-contrast trustedDialog banner at exactly 1088 x 464 px."""
 W,H=PREVIEW_SIZE
 panel_w=455
 image_w=W-panel_w
 # A strict split layout is more robust than placing small text over arbitrary website photography.
 artwork=ImageOps.fit(source.convert('RGB'),(image_w,H),Image.Resampling.LANCZOS,centering=(.5,.5))
 brand=safe_brand_rgb(brand_color)
 # Keep very pale or very dark website colors usable while preserving the hue impression.
 if sum(brand)>690:brand=tuple(max(0,int(v*.72)) for v in brand)
 panel=Image.new('RGB',(panel_w,H),brand)
 result=Image.new('RGB',(W,H),'white')
 result.paste(panel,(0,0));result.paste(artwork,(panel_w,0))
 d=ImageDraw.Draw(result)
 text_color=readable_color(brand)
 accent=(255,255,255) if text_color=='#ffffff' else (17,17,17)
 upper,main,lower,cta=campaign_message(headline)
 left=48;available=panel_w-96
 y=55
 if upper:
  small=fit_font(d,upper,available,30,22,True)
  d.text((left,y),upper,font=small,fill=text_color)
  y+=48
 main_font=fit_font(d,main,available,92,48,True)
 main_box=d.textbbox((0,0),main,font=main_font)
 main_h=main_box[3]-main_box[1]
 d.text((left,y),main,font=main_font,fill=text_color)
 y+=main_h+10
 if lower:
  lower_font=fit_font(d,lower,available,47,31,True)
  d.text((left,y),lower,font=lower_font,fill=text_color)
 # CTA: large and unambiguous, never smaller than 24 px.
 cta_font=fit_font(d,cta,available-52,28,24,True)
 cta_text_w=d.textlength(cta,font=cta_font)
 button_w=min(available,cta_text_w+52);button_h=64
 button_y=H-102
 if text_color=='#ffffff':
  button_fill=(255,255,255);button_text=brand
 else:
  button_fill=(17,17,17);button_text=(255,255,255)
 d.rounded_rectangle((left,button_y,left+button_w,button_y+button_h),radius=18,fill=button_fill)
 d.text((left+26,button_y+16),cta,font=cta_font,fill=button_text)
 # A subtle divider gives stable visual guidance without adding detail.
 d.rectangle((panel_w-2,0,panel_w,H),fill=accent)
 return result

def png_data(image):
 buffer=io.BytesIO();image.save(buffer,'PNG',optimize=False);return buffer.getvalue()

for k,v in {'domain':'','sender':'Absender','subject':'Betreff','preheader':'Preview-Text','color':'#b8ddfd','analysis':None,'generated_preview':None,'generated_avatar':'','selected_image':''}.items():st.session_state.setdefault(k,v)
st.title('trustedDialog Preview Builder')
st.caption('Domain eingeben, Vorschläge automatisch erstellen und anschließend direkt bearbeiten.')

st.subheader('1. Unternehmen analysieren')
d1,d2=st.columns([4,1])
with d1:st.text_input('Für welche Domain soll das trustedDialog Preview generiert werden?',key='domain',placeholder='z. B. www.beispiel.de')
with d2:
 st.write('');st.write('')
 analyze_clicked=st.button('Vorschläge erstellen',type='primary',use_container_width=True)
if analyze_clicked:
 try:
  with st.spinner('Website wird analysiert und die Preview vorbereitet …'):
   result=analyze_site(st.session_state.domain)
   st.session_state.analysis=result
   st.session_state.sender=result['brand']
   st.session_state.subject=result['subject']
   st.session_state.preheader=result['preheader']
   if result['colors']:st.session_state.brand_color=result['colors'][0]
   else:st.session_state.brand_color='#1375d7'
   selected=None;selected_url=''
   for candidate in result['images']:
    try:selected=image_from_url(candidate);selected_url=candidate;break
    except Exception:continue
   if selected is not None:
    st.session_state.selected_image=selected_url
    st.session_state.generated_preview=png_data(generate_preview(selected,result['subject'],st.session_state.brand_color))
   else:st.session_state.generated_preview=None
   for logo in result['logos']:
    try:
     raw,_,content_type=safe_fetch(logo,3000000)
     st.session_state.generated_avatar='data:'+(content_type or 'image/png')+';base64,'+base64.b64encode(raw).decode();break
    except Exception:continue
  st.success('Vorschläge wurden erstellt. Alle Inhalte können unten überschrieben werden.')
 except Exception as error:st.error(f'Die Website konnte nicht analysiert werden: {error}')

analysis=st.session_state.analysis
if analysis:
 with st.expander('Erkannte Website-Informationen',expanded=False):
  st.write(f"**Marke:** {analysis['brand']}")
  if analysis['offers']:st.write('**Gefundene Angebots-Hinweise:** '+' · '.join(analysis['offers'][:5]))
  if analysis['description']:st.write('**Beschreibung:** '+analysis['description'][:350])
  st.caption('Bitte prüfen Sie die vorgeschlagenen Inhalte und stellen Sie sicher, dass die erforderlichen Bild- und Markenrechte vorliegen.')
 if analysis['images']:
  choices=analysis['images']
  chosen=st.selectbox('Alternatives Website-Motiv',choices,index=choices.index(st.session_state.selected_image) if st.session_state.selected_image in choices else 0,format_func=lambda x:x.split('/')[-1][:70] or x)
  if st.button('Ausgewähltes Motiv übernehmen'):
   try:
    img=image_from_url(chosen);st.session_state.selected_image=chosen
    st.session_state.generated_preview=png_data(generate_preview(img,st.session_state.subject,st.session_state.get('brand_color','#1375d7')))
    st.rerun()
   except Exception as error:st.error(f'Das Bild konnte nicht übernommen werden: {error}')

st.subheader('2. Inhalte bearbeiten')
l,r=st.columns([.86,1.14],gap='large')
with l:
 st.text_input('Absender / Marke',key='sender',max_chars=37)
 st.text_input('Betreff',key='subject',max_chars=37)
 st.text_input('Preview-Text',key='preheader',max_chars=37)
 st.color_picker('Fallback-Avatarfarbe',key='color')
 af=st.file_uploader('Avatar / Logo überschreiben',type=['svg','png','jpg','jpeg','webp'],help='SVG wird direkt nach dem Upload im Browser in PNG konvertiert und anschließend nur noch als PNG verwendet.')
 pf=st.file_uploader('Preview-Bild überschreiben (1088 × 464 px)',type=['png','jpg','jpeg','webp'])
 if st.session_state.generated_preview:
  st.download_button('Generiertes Preview-Bild herunterladen',st.session_state.generated_preview,file_name=f"trustedDialog_Preview_{re.sub(r'[^A-Za-z0-9._-]+','_',st.session_state.sender)}_1088x464.png",mime='image/png',use_container_width=True)
sender,subject,pre=display_text(st.session_state.sender),display_text(st.session_state.subject),display_text(st.session_state.preheader)
download_sender=json.dumps(st.session_state.sender or 'Absender',ensure_ascii=False)
avsrc=uri(af) if af else st.session_state.generated_avatar
psrc=uri(pf) if pf else ('data:image/png;base64,'+base64.b64encode(st.session_state.generated_preview).decode() if st.session_state.generated_preview else '')
letters=e(''.join(x[0] for x in st.session_state.sender.split()[:2]).upper() or 'M')
av=f'<img class="avatar" id="uploaded-avatar" data-is-svg="{str(bool(af and af.name.lower().endswith(".svg"))).lower()}" src="{avsrc}">' if avsrc else f'<span class="avatar fallback" style="background:#b8ddfd;color:#1375d7">{letters}</span>'
pv=f'<img class="preview" src="{psrc}">' if psrc else '<div class="preview placeholder">Bild einfügen</div>'
seal=f'<img class="seal" src="{SEAL}" alt="trustedDialog Siegel">'
H=f'''<!doctype html><html><head><meta charset="utf-8"><script src="https://cdn.jsdelivr.net/npm/html2canvas@1.4.1/dist/html2canvas.min.js"></script><style>
*{{box-sizing:border-box}}html,body{{margin:0;background:transparent;font-family:Arial,sans-serif}}.stage{{display:flex;flex-direction:column;align-items:center}}.phone{{position:relative;width:390px;height:780px;border-radius:58px;background:#111;border:2px solid #777;box-shadow:inset 0 0 0 2px #d4d4d4,0 8px 22px #0003}}.phone:before{{content:"";position:absolute;inset:5px;border:1px solid #333;border-radius:53px;z-index:9;pointer-events:none}}.screen{{position:absolute;inset:14px;width:362px;height:752px;overflow:hidden;border-radius:46px;background:#fff;color:#111}}.status{{position:relative;height:43px;padding:13px 23px 0;font-size:14px;font-weight:700}}.island{{position:absolute;top:9px;left:50%;transform:translateX(-50%);width:106px;height:31px;border-radius:18px;background:#090909}}.sright{{position:absolute;right:19px;top:10px;height:23px;display:flex;align-items:center;gap:8px}}.signal{{display:flex;align-items:flex-end;gap:2px;height:15px}}.signal i{{width:4px;background:#111;border-radius:2px}}.signal i:nth-child(1){{height:6px}}.signal i:nth-child(2){{height:9px}}.signal i:nth-child(3){{height:12px}}.signal i:nth-child(4){{height:15px}}.wifi-icon{{width:21px;height:18px;display:block;fill:#111}}.battery{{height:21px;min-width:34px;padding:0 5px;border-radius:7px;background:#111;color:#fff;display:flex;align-items:center;justify-content:center;font-size:12px}}.hdr{{height:60px;display:grid;grid-template-columns:38px 1fr 40px 40px;align-items:center;gap:5px;padding:0 14px}}.round{{width:36px;height:36px;border-radius:50%;background:#fafafa;display:flex;align-items:center;justify-content:center}}.back{{font-size:28px}}.head strong{{display:block;font-size:14px;line-height:17px}}.head small{{display:block;font-size:10px;color:#aaa}}.hicon{{width:21px;height:21px;stroke:#111;fill:none;stroke-width:2.2;stroke-linecap:round;stroke-linejoin:round}}.search{{height:42px;margin:0 17px 12px;border-radius:22px;background:#f4f4f5;display:flex;align-items:center;padding:0 16px;color:#777;font-size:15px}}.receive{{height:34px;border-top:1px solid #ddd;border-bottom:1px solid #ddd;padding:0 17px;display:flex;align-items:center;gap:14px;color:#777;font-size:11px}}.dots{{color:#5caee9;letter-spacing:3px;font-size:16px}}.list{{margin:0 17px}}.row{{display:grid;grid-template-columns:42px minmax(0,1fr) 42px;column-gap:10px;border-bottom:1px solid #ddd;padding:10px 0 9px}}.row.td{{min-height:194px;padding-top:11px}}.avatar{{width:38px;height:38px;border-radius:50%;object-fit:cover;display:flex;align-items:center;justify-content:center;color:#fff;font-size:13px;font-weight:700}}.avatar.fallback{{color:#1375d7}}.content{{min-width:0}}.senderline{{height:18px;display:flex;align-items:center;white-space:nowrap}}.sender{{font-size:13px;line-height:18px;font-weight:700;max-width:166px;overflow:hidden;text-overflow:ellipsis}}.seal{{width:16px;height:16px;flex:0 0 16px;margin-left:4px;object-fit:contain}}.subject,.pre{{height:18px;font-size:13px;line-height:18px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}.pre{{color:#aaa}}.time{{grid-column:3;grid-row:1;text-align:right;color:#aaa;font-size:10px;padding-top:2px}}.pwrap{{grid-column:2/4;margin-top:3px;width:253px;height:96px;border-radius:6px;overflow:hidden}}.preview{{width:100%;height:100%;object-fit:cover}}.placeholder{{background:#ff00e8;color:#fff;display:flex;align-items:center;justify-content:center;font-size:11px}}.standard{{min-height:78px}}.standard .sender{{max-width:185px}}.standard .subject,.standard .pre{{max-width:218px}}.nav{{position:absolute;left:14px;right:14px;bottom:14px;height:67px;display:grid;grid-template-columns:repeat(5,1fr);padding:5px 7px;border-radius:35px;background:#fff;box-shadow:0 1px 18px #0002}}.navitem{{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:2px;border-radius:29px;font-size:11px;font-weight:600}}.navitem.active{{background:#ededed;color:#1873bf}}.nsvg{{width:29px;height:29px;fill:#111;stroke:#111}}.active .nsvg{{fill:#1873bf;stroke:#1873bf}}.home{{position:absolute;left:50%;bottom:5px;transform:translateX(-50%);width:125px;height:4px;border-radius:3px;background:#111}}.downloadbar{{margin-top:12px;text-align:center}}.downloadbtn{{border:1px solid #777;background:#fff;color:#111;border-radius:6px;padding:9px 14px;font:600 13px Arial,sans-serif;cursor:pointer}}.downloadbtn:hover{{background:#f4f4f4}}
</style></head><body><div class="stage"><div class="phone"><div class="screen"><div class="status"><span id="now">09:24</span><span class="island"></span><span class="sright"><span class="signal"><i></i><i></i><i></i><i></i></span><svg class="wifi-icon" viewBox="0 0 24 18" aria-label="WLAN"><path d="M2 6.2C7.6 1.6 16.4 1.6 22 6.2L19.3 9C15.2 5.7 8.8 5.7 4.7 9L2 6.2Z"/><path d="M6.2 10.5C9.5 7.8 14.5 7.8 17.8 10.5L15.1 13.2C13.3 11.8 10.7 11.8 8.9 13.2L6.2 10.5Z"/><path d="M9.9 14.5C11.1 13.5 12.9 13.5 14.1 14.5L12 17L9.9 14.5Z"/></svg><span class="battery">93</span></span></div><div class="hdr"><span class="round back">‹</span><span class="head"><strong>Posteingang</strong><small>trusteddialog01@gmx.net</small></span><span class="round"><svg class="hicon" viewBox="0 0 24 24"><circle cx="12" cy="12" r="8"/><path d="m8.5 12 2.2 2.2 4.8-5"/></svg></span><span class="round"><svg class="hicon" viewBox="0 0 24 24"><path d="M14 5h5v5M19 5l-8 8M17 12v6H6V7h6"/></svg></span></div><div class="search">⌕ &nbsp; Suchen</div><div class="receive"><span class="dots">•••</span>E-Mails empfangen</div><div class="list">
<div class="row td"><div>{av}</div><div class="content"><div class="senderline"><span class="sender">{sender}</span>{seal}</div><div class="subject">{subject}</div><div class="pre">{pre}</div></div><div class="time" data-off="-3"></div><div class="pwrap">{pv}</div></div>
<div class="row standard"><div><span class="avatar fallback" style="background:#b8ddfd;color:#1375d7">OH</span></div><div class="content"><div class="senderline"><span class="sender">Otto Holler</span></div><div class="subject">Gewünschte Bilder</div><div class="pre">Hallo zusammen, anbei findet Ihr die…</div></div><div class="time" data-off="-15"></div></div>
<div class="row standard"><div><img class="avatar" src="{GMX_LOGO}" alt="GMX"></div><div class="content"><div class="senderline"><span class="sender">GMX Magazin</span>{seal}</div><div class="subject">Traumhaus auf Föhr zu gewinnen: 8…</div><div class="pre">Jetzt Lose bei GMX Lotto sichern! W…</div></div><div class="time" data-off="-34"></div></div>
<div class="row standard"><div><span class="avatar fallback" style="background:#b8ddfd;color:#1375d7">SW</span></div><div class="content"><div class="senderline"><span class="sender">Shopping World</span></div><div class="subject">Neue Deals am Wochenende</div><div class="pre">Jetzt entdecken</div></div><div class="time" data-off="-47"></div></div><div class="row standard" style="border:0"><div><span class="avatar fallback" style="background:#b8ddfd;color:#1375d7">FF</span></div><div class="content"><div class="senderline"><span class="sender">Fred Fritt</span></div><div class="subject">Klassentreffen</div><div class="pre">Hallo zusammen, vielen Dank für das to…</div></div><div class="time" data-off="-59">11:19</div></div></div>
<div class="nav"><div class="navitem active"><svg class="nsvg" viewBox="0 0 32 32"><rect x="3" y="7" width="26" height="19" rx="1" fill="none" stroke-width="2"/><path d="M4 8l12 10L28 8" fill="none" stroke-width="2"/></svg>E-Mail</div><div class="navitem"><svg class="nsvg" viewBox="0 0 32 32"><path d="M4 9h10l3 3h11v15H4z"/></svg>Dateien</div><div class="navitem"><svg class="nsvg" viewBox="0 0 32 32"><rect x="7" y="4" width="21" height="22" rx="2" fill="none" stroke-width="3"/><path d="m9 23 6-7 4 4 3-3 5 6z"/></svg>Fotos</div><div class="navitem"><svg class="nsvg" viewBox="0 0 32 32"><rect x="6" y="19" width="5" height="9" rx="2"/><rect x="13" y="14" width="5" height="14" rx="2"/><rect x="20" y="9" width="5" height="19" rx="2"/><rect x="27" y="4" width="5" height="24" rx="2"/></svg>Mobil</div><div class="navitem"><svg class="nsvg" viewBox="0 0 32 32"><rect x="5" y="3" width="22" height="26" fill="none" stroke-width="2.5"/><path d="M9 8h14M9 12h14M9 17h6M17 17h6M17 21h6M17 25h6" fill="none" stroke-width="2"/></svg>News</div></div><div class="home"></div></div></div></div>
<div class="downloadbar"><button class="downloadbtn" onclick="downloadPreview()">GMX-Vorschau als PNG herunterladen</button></div>
<script>
const p=n=>String(n).padStart(2,'0'),fmt=d=>p(d.getHours())+':'+p(d.getMinutes());
function tick(){{let n=new Date();document.getElementById('now').textContent=fmt(n);document.querySelectorAll('[data-off]').forEach(x=>x.textContent=fmt(new Date(n.getTime()+Number(x.dataset.off)*60000)))}}
tick();setInterval(tick,30000);
async function svgAvatarToPngImmediately(){{
 const img=document.getElementById('uploaded-avatar');
 if(!img || img.dataset.isSvg!=='true') return;
 await new Promise(resolve=>{{if(img.complete) resolve(); else {{img.onload=resolve;img.onerror=resolve;}}}});
 const source=new Image();
 await new Promise((resolve,reject)=>{{source.onload=resolve;source.onerror=reject;source.src=img.currentSrc||img.src;}});
 const size=256;
 const canvas=document.createElement('canvas');canvas.width=size;canvas.height=size;
 const ctx=canvas.getContext('2d');ctx.clearRect(0,0,size,size);
 const sw=source.naturalWidth||size,sh=source.naturalHeight||size;
 const scale=Math.max(size/sw,size/sh),dw=sw*scale,dh=sh*scale;
 ctx.drawImage(source,(size-dw)/2,(size-dh)/2,dw,dh);
 img.src=canvas.toDataURL('image/png');
 img.removeAttribute('data-is-svg');
}}
svgAvatarToPngImmediately().catch(err=>console.warn('SVG-to-PNG conversion failed',err));
async function downloadPreview(){{
 const button=document.querySelector('.downloadbtn');
 const phone=document.querySelector('.phone');
 const original=button.textContent;
 try{{
  button.disabled=true;button.textContent='PNG wird erstellt…';
  if(typeof html2canvas==='undefined') throw new Error('html2canvas konnte nicht geladen werden');
  await document.fonts.ready;
  await Promise.all(Array.from(phone.querySelectorAll('img')).map(img=>img.complete ? Promise.resolve() : new Promise(resolve=>{{img.onload=resolve;img.onerror=resolve;}})));
  const canvas=await html2canvas(phone,{{
   backgroundColor:null,
   scale:2,
   useCORS:true,
   allowTaint:false,
   logging:false,
   width:390,
   height:780,
   scrollX:0,
   scrollY:0,
   onclone:(doc)=>{{
    const clonedPhone=doc.querySelector('.phone');
    clonedPhone.style.background='#111';
    clonedPhone.style.border='2px solid #777';
    clonedPhone.style.boxShadow='inset 0 0 0 2px #d4d4d4';
    clonedPhone.style.opacity='1';
    doc.querySelectorAll('img.preview').forEach(img=>{{
     const wrap=img.closest('.pwrap');
     if(wrap){{
      wrap.style.backgroundImage='url("'+img.src+'")';
      wrap.style.backgroundSize='cover';
      wrap.style.backgroundPosition='center center';
      wrap.style.backgroundRepeat='no-repeat';
      img.style.visibility='hidden';
     }}
    }});

    doc.querySelectorAll('img.avatar').forEach(img=>{{
     img.style.width='38px';img.style.height='38px';
     img.style.minWidth='38px';img.style.minHeight='38px';
     img.style.maxWidth='38px';img.style.maxHeight='38px';
     img.style.borderRadius='50%';img.style.objectFit='cover';
     img.style.objectPosition='center center';img.style.display='block';img.style.visibility='visible';
    }});
   }}
  }});
  const rawSender={download_sender};
  const safeSender=String(rawSender).trim().replace(/[\\/:*?"<>|]+/g,'_')||'Absender';
  const blob=await new Promise(resolve=>canvas.toBlob(resolve,'image/png'));
  if(!blob) throw new Error('PNG-Blob konnte nicht erzeugt werden');
  const url=URL.createObjectURL(blob);
  const link=document.createElement('a');
  link.download='GMX_trustedDialogPreview_'+safeSender+'.png';
  link.href=url;
  document.body.appendChild(link);link.click();link.remove();
  setTimeout(()=>URL.revokeObjectURL(url),1000);
 }}catch(err){{
  console.error(err);
  alert('Die PNG-Datei konnte nicht erzeugt werden: '+err.message);
 }}finally{{button.disabled=false;button.textContent=original;}}
}}
</script></body></html>'''
with r:
 st.subheader('3. GMX Live-Vorschau');st.caption('Smartphone · GMX.DE · iOS');components.html(H,height=860,scrolling=False)
st.caption('Echtes trustedDialog SVG-Siegel · SVG-Avatar-Upload · Live-Zeit mit früheren Mailzeiten · korrigierter Vier-Punkte-Footer')
