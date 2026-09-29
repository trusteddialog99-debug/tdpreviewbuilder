import io
import re
import socket
import ipaddress
from urllib.parse import urljoin, urlparse

import requests
import streamlit as st
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont, ImageOps

st.set_page_config(page_title="trustedDialog Preview Builder", page_icon="✉️", layout="wide")
MAX_TEXT = 29
PREVIEW_SIZE = (1088, 464)
UA = "Mozilla/5.0 (compatible; UIM-trustedDialog-Preview-Builder/1.1)"


def font(size, bold=False):
    paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for p in paths:
        try: return ImageFont.truetype(p, size)
        except OSError: pass
    return ImageFont.load_default()


def normalize_url(v):
    v=(v or "").strip()
    if v and not v.startswith(("http://","https://")): v="https://"+v
    return v


def public_url(url):
    try:
        p=urlparse(url)
        if p.scheme not in ("http","https") or not p.hostname: return False
        for info in socket.getaddrinfo(p.hostname, p.port or 443, type=socket.SOCK_STREAM):
            ip=ipaddress.ip_address(info[4][0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast: return False
        return True
    except Exception: return False


def safe_get(url,max_bytes=5000000):
    if not public_url(url): raise ValueError("URL nicht öffentlich erreichbar oder blockiert.")
    with requests.get(url,headers={"User-Agent":UA},timeout=10,stream=True,allow_redirects=True) as r:
        r.raise_for_status()
        if not public_url(r.url): raise ValueError("Weiterleitung blockiert.")
        b=bytearray()
        for ch in r.iter_content(65536):
            b.extend(ch)
            if len(b)>max_bytes: raise ValueError("Datei zu groß.")
        return bytes(b),r.url


def meta(soup,*keys):
    for key in keys:
        n=soup.find("meta",attrs={"property":key}) or soup.find("meta",attrs={"name":key})
        if n and n.get("content"): return n["content"].strip()
    return ""


def uniq(xs):
    out=[]; seen=set()
    for x in xs:
        if x and x not in seen: seen.add(x); out.append(x)
    return out


def analyze_website(url):
    raw,final=safe_get(url,2500000)
    soup=BeautifulSoup(raw,"html.parser")
    title=meta(soup,"og:site_name") or (soup.title.string.strip() if soup.title and soup.title.string else "")
    brand=(re.split(r"[|–—-]",title)[0].strip() if title else urlparse(final).hostname.replace("www.",""))
    text=" ".join(soup.stripped_strings)
    offers=[]
    for pat in [r"\b\d{1,2}\s?%\s*(?:Rabatt|sparen|off)\b",r"\b\d+(?:[,.]\d{1,2})?\s?€\s*(?:Rabatt|sparen|Gutschein)?\b",r"\b(?:Willkommensrabatt|Gutscheincode|Sale|Angebot|Gratis Versand)\b[^.!?]{0,80}"]:
        offers += re.findall(pat,text,flags=re.I)
    logos=[]; imgs=[meta(soup,"og:image","twitter:image")]
    for el in soup.find_all("img"):
        src=el.get("src") or el.get("data-src") or el.get("data-lazy-src")
        if not src: continue
        marker=(el.get("alt","")+" "+" ".join(el.get("class",[]))+" "+el.get("id","")).lower()
        if "logo" in marker: logos.append(urljoin(final,src))
        elif not src.lower().endswith(".svg"): imgs.append(urljoin(final,src))
    return {"brand":brand[:75],"offers":uniq([re.sub(r"\s+"," ",x).strip() for x in offers])[:8],"logos":uniq(logos)[:8],"images":uniq([urljoin(final,x) for x in imgs if x])[:12]}


def remote_image(url):
    raw,_=safe_get(url,8000000); im=Image.open(io.BytesIO(raw)); im.load(); return im.convert("RGB")


def cover(im,size): return ImageOps.fit(im.convert("RGB"),size,method=Image.Resampling.LANCZOS)

def rounded(im,r):
    im=im.convert("RGBA"); mask=Image.new("L",im.size); ImageDraw.Draw(mask).rounded_rectangle((0,0,*im.size),radius=r,fill=255); im.putalpha(mask); return im

def trunc(t,n=MAX_TEXT): return t if len(t)<=n else t[:n-3]+"..."

def initials_avatar(name,color):
    im=Image.new("RGBA",(200,200),color); d=ImageDraw.Draw(im); s="".join(w[0] for w in name.split()[:2] if w).upper() or "A"; f=font(76,True); b=d.textbbox((0,0),s,font=f); d.text(((200-(b[2]-b[0]))/2,(200-(b[3]-b[1]))/2-5),s,font=f,fill="white"); return im


def placeholder_asset(source):
    if source is not None: return cover(source,PREVIEW_SIZE)
    im=Image.new("RGB",PREVIEW_SIZE,"#ff00e8"); d=ImageDraw.Draw(im); label="Bild einfügen"; f=font(70); b=d.textbbox((0,0),label,font=f); d.text(((PREVIEW_SIZE[0]-(b[2]-b[0]))/2,(PREVIEW_SIZE[1]-(b[3]-b[1]))/2-8),label,font=f,fill="white"); return im


def mockup(sender,subject,preheader,avatar,asset):
    # Portrait canvas modelled closely on the supplied WEB.DE mobile reference.
    W,H=708,1408; im=Image.new("RGBA",(W,H),(255,255,255,0)); d=ImageDraw.Draw(im)
    # phone shell
    d.rounded_rectangle((27,8,681,1397),radius=96,fill="#171717",outline="#000",width=3)
    d.rounded_rectangle((36,18,672,1387),radius=88,fill="#f9f9f9",outline="#c8c8c8",width=3)
    d.rounded_rectangle((49,31,659,1374),radius=77,fill="white")
    # dynamic island/status
    d.rounded_rectangle((288,44,418,86),radius=25,fill="#0f0f0f")
    d.ellipse((396,58,405,67),fill="#101c3a")
    d.text((72,55),"10:03",font=font(25,True),fill="#111")
    d.text((590,54),"•••  ▪",font=font(19,True),fill="#333")
    # header
    d.ellipse((76,103,132,159),fill="#f7f7f7"); d.text((94,111),"‹",font=font(43),fill="#111")
    d.text((150,103),"Posteingang",font=font(28,True),fill="#111")
    d.text((150,137),"trusteddialog01@gmx.net",font=font(16),fill="#8b8b8b")
    d.ellipse((489,104,551,166),fill="#fafafa"); d.ellipse((506,120,534,148),outline="#111",width=3); d.text((512,119),"✓",font=font(21,True),fill="#111")
    d.ellipse((567,104,629,166),fill="#fafafa"); d.rectangle((586,124,612,147),outline="#111",width=3); d.line((598,133,616,116),fill="#111",width=4)
    # search
    d.rounded_rectangle((76,181,632,246),radius=31,fill="#f1f1f3"); d.ellipse((96,201,119,224),outline="#333",width=3); d.line((114,220,126,232),fill="#333",width=3); d.text((139,198),"Suchen",font=font(24),fill="#777")
    d.line((72,272,637,272),fill="#dedede",width=2)
    d.text((78,286),"•••",font=font(22,True),fill="#45a9e8"); d.text((143,289),"E-Mails empfangen",font=font(17),fill="#777")
    d.line((72,326,637,326),fill="#dedede",width=2)
    # td row
    av=rounded(cover(avatar,(67,67)),34); im.paste(av,(94,350),av)
    d.text((180,352),trunc(sender),font=font(24,True),fill="#101010")
    sx=180+int(d.textlength(trunc(sender),font=font(24,True)))+10
    d.ellipse((sx,357,sx+23,380),fill="#4e8dcb"); d.text((sx+5,354),"✓",font=font(17,True),fill="white")
    d.text((579,356),"09:33",font=font(17),fill="#9a9a9a")
    d.text((180,393),trunc(subject),font=font(22),fill="#111")
    d.text((180,432),trunc(preheader),font=font(22),fill="#afafaf")
    art=rounded(cover(asset,(447,196)),8); im.paste(art,(185,468),art)
    d.line((101,683,638,683),fill="#dedede",width=2)
    # Inbox rows
    rows=[("OH","Otto Holler","Gewünschte Bilder","Hallo zusammen, anbei findet ihr die...","09:21","#8baad0",False),
          ("GMX","GMX Magazin","Traumhaus auf Föhr zu gewinnen: 8...","Jetzt Lose bei GMX Lotto sichern! W...","09:02","#1670c5",True),
          ("SW","Shopping World","Neue Deals am Wochenende","Jetzt entdecken","08:49","#8baad0",False)]
    y=710
    for initials,s,sub,pre,t,c,seal in rows:
        d.ellipse((100,y,166,y+66),fill=c); f=font(18 if len(initials)>2 else 22,True); b=d.textbbox((0,0),initials,font=f); d.text((133-(b[2]-b[0])/2,y+33-(b[3]-b[1])/2-2),initials,font=f,fill="white")
        d.text((181,y+1),s,font=font(22,True),fill="#111")
        if seal:
            ex=181+int(d.textlength(s,font=font(22,True)))+8; d.ellipse((ex,y+5,ex+22,y+27),fill="#4e8dcb"); d.text((ex+5,y+2),"✓",font=font(16,True),fill="white")
        d.text((579,y+5),t,font=font(16),fill="#9b9b9b"); d.text((181,y+38),sub,font=font(20),fill="#111"); d.text((181,y+73),pre,font=font(20),fill="#aaa")
        d.line((101,y+112,638,y+112),fill="#dedede",width=2); y+=145
    # bottom nav
    d.rounded_rectangle((77,1228,632,1340),radius=52,fill=(250,250,250,245),outline="#efefef",width=2)
    nav=[("✉","E-Mail",112,"#2879b9"),("■","Dateien",221,"#222"),("▣","Fotos",327,"#222"),("✹","Vorteile",438,"#222"),("▤","News",548,"#222")]
    for icon,label,x,c in nav:
        d.text((x,1250),icon,font=font(27,True),fill=c); d.text((x-7,1294),label,font=font(13,True),fill=c)
    d.ellipse((137,1243,164,1270),fill="#d52f2f"); d.text((145,1241),"5",font=font(16,True),fill="white")
    d.rounded_rectangle((275,1362,432,1368),radius=4,fill="#111")
    return im

for k,v in {"sender":"Absender","subject":"Betreff","preheader":"Preview","brand_color":"#ff00e8","analysis":None,"remote_avatar":None,"remote_preview":None}.items(): st.session_state.setdefault(k,v)

st.title("trustedDialog Preview Builder")
st.caption("MVP mit CI-naher WEB.DE-Mobile-Vorschau auf Basis der gelieferten Referenz.")
with st.expander("Website-Analyse",expanded=False):
    c1,c2=st.columns([3,1]); domain=c1.text_input("Domain",placeholder="z. B. mey.com")
    if c2.button("Analysieren",type="primary",use_container_width=True):
        try:
            r=analyze_website(normalize_url(domain)); st.session_state.analysis=r; st.session_state.sender=trunc(r["brand"]); st.success("Website analysiert.")
        except Exception as e: st.error(str(e))
    r=st.session_state.analysis
    if r:
        if r["logos"]: st.selectbox("Avatar-Kandidat",["Nicht verwenden"]+r["logos"],key="remote_avatar")
        if r["images"]: st.selectbox("Preview-Bild-Kandidat",["Nicht verwenden"]+r["images"],key="remote_preview")

left,right=st.columns([0.82,1.18],gap="large")
with left:
    st.subheader("Inhalte")
    st.text_input("Absender",key="sender"); st.caption(f"{len(st.session_state.sender)}/29")
    st.text_input("Betreff",key="subject"); st.caption(f"{len(st.session_state.subject)}/29")
    st.text_input("Preview",key="preheader"); st.caption(f"{len(st.session_state.preheader)}/29")
    avatar_up=st.file_uploader("Avatar / Logo",type=["png","jpg","jpeg","webp"])
    preview_up=st.file_uploader("trustedDialog Preview Bild",type=["png","jpg","jpeg","webp"])
    st.color_picker("Fallback-Farbe für Avatar",key="brand_color")

avatar=None
if avatar_up:
    try: avatar=Image.open(avatar_up).convert("RGBA")
    except: pass
elif st.session_state.remote_avatar and st.session_state.remote_avatar!="Nicht verwenden":
    try: avatar=remote_image(st.session_state.remote_avatar).convert("RGBA")
    except: pass
if avatar is None: avatar=initials_avatar(st.session_state.sender,st.session_state.brand_color)
source=None
if preview_up:
    try: source=Image.open(preview_up).convert("RGB")
    except: pass
elif st.session_state.remote_preview and st.session_state.remote_preview!="Nicht verwenden":
    try: source=remote_image(st.session_state.remote_preview)
    except: pass
asset=placeholder_asset(source); phone=mockup(st.session_state.sender,st.session_state.subject,st.session_state.preheader,avatar,asset)
buf=io.BytesIO(); phone.save(buf,"PNG")
with right:
    st.subheader("WEB.DE Live-Vorschau")
    st.image(phone,use_container_width=False,width=430)
    st.download_button("Mockup als PNG herunterladen",buf.getvalue(),file_name="WEBDE_trustedDialog_Mockup.png",mime="image/png",use_container_width=False)
st.caption("Beispielhafte Darstellung. Die Oberfläche wurde für den MVP visuell an die bereitgestellte WEB.DE-Referenz angelehnt.")
