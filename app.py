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
UA = "Mozilla/5.0 (compatible; UIM-trustedDialog-Preview-Builder/1.0)"

# ---------- Helpers ----------
def font(size, bold=False):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for p in candidates:
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            pass
    return ImageFont.load_default()


def normalize_url(value):
    value = (value or "").strip()
    if not value:
        return ""
    if not value.startswith(("http://", "https://")):
        value = "https://" + value
    return value


def is_public_http_url(url):
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            return False
        infos = socket.getaddrinfo(parsed.hostname, parsed.port or 443, type=socket.SOCK_STREAM)
        for info in infos:
            ip = ipaddress.ip_address(info[4][0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
                return False
        return True
    except Exception:
        return False


def safe_get(url, max_bytes=5_000_000):
    if not is_public_http_url(url):
        raise ValueError("Die URL ist nicht öffentlich erreichbar oder wurde aus Sicherheitsgründen blockiert.")
    with requests.get(url, headers={"User-Agent": UA}, timeout=10, stream=True, allow_redirects=True) as r:
        r.raise_for_status()
        final_url = r.url
        if not is_public_http_url(final_url):
            raise ValueError("Die Weiterleitung wurde aus Sicherheitsgründen blockiert.")
        data = bytearray()
        for chunk in r.iter_content(64 * 1024):
            data.extend(chunk)
            if len(data) > max_bytes:
                raise ValueError("Die Datei ist zu groß.")
        return bytes(data), r.headers.get("content-type", ""), final_url


def meta_content(soup, *keys):
    for key in keys:
        node = soup.find("meta", attrs={"property": key}) or soup.find("meta", attrs={"name": key})
        if node and node.get("content"):
            return node["content"].strip()
    return ""


def unique(items):
    seen, out = set(), []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out


def analyze_website(url):
    raw, content_type, final_url = safe_get(url, max_bytes=2_500_000)
    soup = BeautifulSoup(raw, "html.parser")
    title = meta_content(soup, "og:site_name") or (soup.title.string.strip() if soup.title and soup.title.string else "")
    brand = re.split(r"[|–—-]", title)[0].strip() if title else urlparse(final_url).hostname.replace("www.", "")
    description = meta_content(soup, "og:description", "description")

    text = " ".join(soup.stripped_strings)
    offer_patterns = [
        r"\b\d{1,2}\s?%\s*(?:Rabatt|sparen|off)\b",
        r"\b\d+(?:[,.]\d{1,2})?\s?€\s*(?:Rabatt|sparen|Gutschein)?\b",
        r"\b(?:Willkommensrabatt|Gutscheincode|Sale|Angebot|Gratis Versand)\b[^.!?]{0,80}",
    ]
    offers = []
    for pattern in offer_patterns:
        offers.extend(re.findall(pattern, text, flags=re.I))
    offers = unique([re.sub(r"\s+", " ", x).strip() for x in offers])[:8]

    logo_urls = []
    for rel in ["icon", "shortcut icon", "apple-touch-icon"]:
        for el in soup.find_all("link", rel=lambda v: v and rel in " ".join(v if isinstance(v, list) else [v]).lower()):
            if el.get("href"):
                logo_urls.append(urljoin(final_url, el["href"]))
    for el in soup.find_all("img"):
        src = el.get("src") or el.get("data-src")
        marker = " ".join([el.get("alt", ""), el.get("class", [""])[0] if el.get("class") else "", el.get("id", "")]).lower()
        if src and "logo" in marker:
            logo_urls.append(urljoin(final_url, src))

    image_urls = [meta_content(soup, "og:image", "twitter:image")]
    for el in soup.find_all("img"):
        src = el.get("src") or el.get("data-src") or el.get("data-lazy-src")
        if not src:
            continue
        w = str(el.get("width", "")); h = str(el.get("height", ""))
        marker = (el.get("alt", "") + " " + " ".join(el.get("class", []))).lower()
        if "logo" not in marker and "icon" not in marker and not src.lower().endswith(".svg"):
            if (w.isdigit() and int(w) >= 500) or not w:
                image_urls.append(urljoin(final_url, src))

    return {
        "url": final_url,
        "brand": brand[:75],
        "description": description,
        "offers": offers,
        "logos": unique(logo_urls)[:8],
        "images": unique([urljoin(final_url, x) for x in image_urls if x])[:12],
    }


def load_remote_image(url):
    raw, _, _ = safe_get(url, max_bytes=8_000_000)
    img = Image.open(io.BytesIO(raw))
    img.load()
    return img.convert("RGB")


def initial_avatar(name, color):
    img = Image.new("RGBA", (300, 300), color)
    d = ImageDraw.Draw(img)
    initials = "".join([w[0] for w in name.split()[:2] if w]).upper() or "M"
    f = font(114, True)
    box = d.textbbox((0, 0), initials, font=f)
    d.text(((300-(box[2]-box[0]))/2, (300-(box[3]-box[1]))/2-7), initials, font=f, fill="white")
    return img


def cover(img, size):
    return ImageOps.fit(img.convert("RGB"), size, method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))


def rounded(img, radius):
    img = img.convert("RGBA")
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, img.width, img.height), radius=radius, fill=255)
    img.putalpha(mask)
    return img


def truncate(text, limit=MAX_TEXT):
    text = text or ""
    return text if len(text) <= limit else text[:max(0, limit-3)] + "..."


def make_suggestions(brand, offers, description):
    offer = offers[0] if offers else "Vorteile entdecken"
    if "%" in offer:
        pct = re.search(r"\d{1,2}\s?%", offer)
        desc = (pct.group(0) + " Rabatt") if pct else "Rabatt sichern"
    elif "€" in offer:
        euro = re.search(r"\d+(?:[,.]\d{1,2})?\s?€", offer)
        desc = (euro.group(0) + " Rabatt") if euro else "Gutschein sichern"
    else:
        desc = "Vorteil sichern"
    return {
        "sender": truncate(brand),
        "subject": truncate(offer if offers else f"Neu bei {brand}"),
        "preheader": truncate("Jetzt Angebot entdecken"),
        "coupon_desc": truncate(desc, 25),
        "coupon_code": "WELCOME10",
    }


def build_preview_asset(source, headline, cta, brand_color):
    if source is None:
        bg = Image.new("RGB", PREVIEW_SIZE, brand_color)
    else:
        bg = cover(source, PREVIEW_SIZE)
        overlay = Image.new("RGBA", PREVIEW_SIZE, (0, 0, 0, 0))
        ImageDraw.Draw(overlay).rectangle((0, 0, 520, PREVIEW_SIZE[1]), fill=(0, 0, 0, 115))
        bg = Image.alpha_composite(bg.convert("RGBA"), overlay).convert("RGB")
    d = ImageDraw.Draw(bg)
    if headline:
        words = headline.split()
        lines, line = [], ""
        for w in words:
            test = (line + " " + w).strip()
            if d.textlength(test, font=font(58, True)) > 450 and line:
                lines.append(line); line = w
            else:
                line = test
        if line: lines.append(line)
        y = 104
        for ln in lines[:3]:
            d.text((56, y), ln, font=font(58, True), fill="white", stroke_width=1, stroke_fill=(0,0,0))
            y += 70
    if cta:
        box = d.textbbox((0, 0), cta, font=font(34, True))
        w = box[2]-box[0]+54
        d.rounded_rectangle((56, 342, 56+w, 414), radius=18, fill="white")
        d.text((83, 357), cta, font=font(34, True), fill=brand_color)
    return bg


def build_inbox_mockup(sender, subject, preheader, coupon_desc, coupon_code, days, avatar, asset):
    W, H = 900, 1500
    canvas = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(canvas)
    blue = "#0066B3"; light = "#F4F6F8"; grey = "#66717A"
    d.rectangle((0, 0, W, 116), fill=blue)
    d.text((48, 34), "WEB.DE", font=font(48, True), fill="white")
    d.text((650, 45), "Posteingang", font=font(30, True), fill="white")
    d.rounded_rectangle((35, 145, 865, 220), radius=38, fill=light)
    d.text((83, 165), "Postfach durchsuchen", font=font(27), fill="#7A8288")
    d.text((42, 253), "Posteingang", font=font(37, True), fill="#1E252B")
    d.text((744, 263), "14:14", font=font(25), fill=grey)

    # focused trustedDialog card
    card = (28, 325, 872, 1105)
    d.rounded_rectangle(card, radius=22, fill="white", outline="#D9DEE3", width=2)
    av = cover(avatar.convert("RGB"), (92, 92))
    av = rounded(av, 46)
    canvas.paste(av, (60, 365), av)
    d.text((177, 360), truncate(sender), font=font(34, True), fill="#20252A")
    # trustedDialog seal approximation for mockup
    d.ellipse((177 + int(d.textlength(truncate(sender), font=font(34, True))) + 14, 367,
               177 + int(d.textlength(truncate(sender), font=font(34, True))) + 48, 401), fill="#1685E5")
    d.text((177 + int(d.textlength(truncate(sender), font=font(34, True))) + 22, 368), "✓", font=font(24, True), fill="white")
    d.text((755, 367), "12:04", font=font(23), fill=grey)
    d.text((177, 412), truncate(subject), font=font(31, True), fill="#252A2E")
    d.text((177, 458), truncate(preheader), font=font(27), fill=grey)

    preview = rounded(cover(asset, (750, 320)), 18)
    canvas.paste(preview, (91, 525), preview)

    if coupon_code:
        d.rounded_rectangle((91, 875, 650, 958), radius=30, fill="#F4FAF2", outline="#75A65C", width=3)
        d.text((119, 897), coupon_desc, font=font(27, True), fill="#3B4A3C")
        x = 119 + int(d.textlength(coupon_desc + " ", font=font(27, True)))
        d.text((x, 897), coupon_code, font=font(27, True), fill="#2878C7")
        d.text((710, 899), f"{days} Tag" if days == 1 else f"{days} Tage", font=font(26, True), fill="#62A23C")

    # surrounding inbox rows
    rows = [
        ("WEB.DE informiert", "Neue Funktionen im Postfach", "Alles Wichtige auf einen Blick"),
        ("Reise Newsletter", "Inspiration für Ihre nächste Reise", "Angebote und Tipps entdecken"),
        ("Shopping Magazin", "Neuheiten der Woche", "Ausgewählte Empfehlungen"),
    ]
    y = 1145
    colors = ["#ECA759", "#74B6DE", "#A48BCC"]
    for i, (s, sub, pre) in enumerate(rows):
        d.line((35, y-16, 865, y-16), fill="#E6E8EA", width=2)
        d.ellipse((55, y, 119, y+64), fill=colors[i])
        d.text((78, y+15), s[0], font=font(27, True), fill="white")
        d.text((145, y-2), s, font=font(27, True), fill="#252A2E")
        d.text((145, y+34), sub, font=font(25), fill="#343B40")
        d.text((145, y+68), pre, font=font(23), fill=grey)
        y += 125
    return canvas


def image_bytes(img, fmt="PNG"):
    b = io.BytesIO(); img.save(b, format=fmt, quality=100); return b.getvalue()


# ---------- State ----------
def defaults():
    return {
        "sender": "Ihre Marke", "subject": "Jetzt Vorteile entdecken", "preheader": "Angebot im Postfach ansehen",
        "coupon_desc": "10 % Rabatt:", "coupon_code": "WELCOME10", "brand_color": "#006B52",
        "headline": "Jetzt Angebot sichern", "cta": "Jetzt entdecken", "days": 3,
        "analysis": None, "remote_avatar": None, "remote_preview": None,
    }
for k, v in defaults().items():
    st.session_state.setdefault(k, v)

st.title("trustedDialog Preview Builder")
st.caption("Interaktiver MVP für ein WEB.DE-Mobile-Mockup. Alle Vorschläge können überschrieben werden.")

with st.expander("1. Website analysieren und Vorschläge übernehmen", expanded=True):
    c1, c2 = st.columns([3, 1])
    domain = c1.text_input("Domain oder Website", placeholder="z. B. www.mey.com")
    if c2.button("Website analysieren", type="primary", use_container_width=True):
        try:
            with st.spinner("Website wird analysiert …"):
                result = analyze_website(normalize_url(domain))
            st.session_state.analysis = result
            sug = make_suggestions(result["brand"], result["offers"], result["description"])
            for k, v in sug.items(): st.session_state[k] = v
            st.success("Analyse abgeschlossen. Texte und Assets wurden als Vorschläge übernommen.")
        except Exception as e:
            st.error(f"Die Website konnte nicht verarbeitet werden: {e}")

    result = st.session_state.analysis
    if result:
        st.markdown(f"**Erkannte Marke:** {result['brand']}")
        if result["offers"]:
            st.write("**Gefundene Angebots-Hinweise:** " + " · ".join(result["offers"][:5]))
        if result["logos"]:
            st.selectbox("Logo-/Avatar-Kandidat", ["Nicht verwenden"] + result["logos"], key="remote_avatar")
        if result["images"]:
            st.selectbox("Bildkandidat von der Website", ["Nicht verwenden"] + result["images"], key="remote_preview")
        st.caption("Bitte nur Bilder verwenden, für die entsprechende Nutzungsrechte vorliegen.")

left, right = st.columns([1.02, 1.25], gap="large")

with left:
    st.subheader("2. Inhalte gestalten")
    st.text_input("Absendername", max_chars=75, key="sender")
    st.caption(f"Vorschau: {len(st.session_state.sender)}/29 Zeichen")
    st.text_input("Betreff", max_chars=75, key="subject")
    st.caption(f"Vorschau: {len(st.session_state.subject)}/29 Zeichen")
    st.text_input("Vorschautext", max_chars=75, key="preheader")
    st.caption(f"Vorschau: {len(st.session_state.preheader)}/29 Zeichen")

    st.markdown("#### Avatar")
    avatar_upload = st.file_uploader("Avatar hochladen", type=["png", "jpg", "jpeg", "webp"], key="avatar_upload")
    st.color_picker("Markenfarbe / Initialen-Avatar", key="brand_color")

    st.markdown("#### Preview-Bild")
    preview_upload = st.file_uploader("Bild hochladen", type=["png", "jpg", "jpeg", "webp"], key="preview_upload")
    st.text_input("Headline im Bild", key="headline")
    st.text_input("CTA im Bild", key="cta")

    st.markdown("#### Gutschein")
    st.text_input("Gutschein-Beschreibung", max_chars=50, key="coupon_desc")
    st.text_input("Gutscheincode", max_chars=50, key="coupon_code")
    st.number_input("Restlaufzeit in Tagen", min_value=1, max_value=99, key="days")

    coupon_ok = len(st.session_state.coupon_code) == 0 or (2 <= len(st.session_state.coupon_code) <= 50 and not re.search(r"[^\x00-\x7F]", st.session_state.coupon_code))
    if not coupon_ok:
        st.warning("Der Gutscheincode muss 2 bis 50 Zeichen enthalten und darf keine Emojis enthalten.")

# Resolve images
avatar_img = None
if avatar_upload:
    try: avatar_img = Image.open(avatar_upload).convert("RGBA")
    except Exception: st.warning("Der Avatar konnte nicht gelesen werden.")
elif st.session_state.remote_avatar and st.session_state.remote_avatar != "Nicht verwenden":
    try: avatar_img = load_remote_image(st.session_state.remote_avatar).convert("RGBA")
    except Exception as e: st.warning(f"Der gewählte Avatar konnte nicht geladen werden: {e}")
if avatar_img is None:
    avatar_img = initial_avatar(st.session_state.sender, st.session_state.brand_color)

source_img = None
if preview_upload:
    try: source_img = Image.open(preview_upload).convert("RGB")
    except Exception: st.warning("Das Preview-Bild konnte nicht gelesen werden.")
elif st.session_state.remote_preview and st.session_state.remote_preview != "Nicht verwenden":
    try: source_img = load_remote_image(st.session_state.remote_preview)
    except Exception as e: st.warning(f"Das gewählte Website-Bild konnte nicht geladen werden: {e}")

asset = build_preview_asset(source_img, st.session_state.headline, st.session_state.cta, st.session_state.brand_color)
mockup = build_inbox_mockup(
    st.session_state.sender, st.session_state.subject, st.session_state.preheader,
    st.session_state.coupon_desc, st.session_state.coupon_code if coupon_ok else "",
    st.session_state.days, avatar_img, asset
)

with right:
    st.subheader("3. WEB.DE Live-Vorschau")
    mode = st.radio("Ansicht", ["Gesamtes Postfach", "Preview-Bild 1088 × 464 px"], horizontal=True)
    if mode == "Gesamtes Postfach":
        st.image(mockup, use_container_width=True)
    else:
        st.image(asset, use_container_width=True)

    st.markdown("#### Export")
    e1, e2 = st.columns(2)
    e1.download_button(
        "WEB.DE-Mockup als PNG", image_bytes(mockup),
        file_name="WEBDE_trustedDialog_Preview.png", mime="image/png", use_container_width=True
    )
    e2.download_button(
        "Preview-Bild als PNG", image_bytes(asset),
        file_name="trustedDialog_Preview_1088x464.png", mime="image/png", use_container_width=True
    )

st.divider()
st.caption("Beispielhafte Darstellung. Das Mockup dient der Visualisierung und ersetzt keine technische oder rechtliche Freigabe.")
