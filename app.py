import base64
import html
import io
import ipaddress
import json
import re
import socket
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

import requests
import streamlit as st
import streamlit.components.v1 as components
from bs4 import BeautifulSoup
from PIL import Image, ImageColor, ImageDraw, ImageFont, ImageOps

st.set_page_config(page_title="trustedDialog Preview Builder", page_icon="✉️", layout="wide")

SEAL_URL = "https://img.ui-portal.de/trusteddialog/trustlogo/trusted-sign_GMX.svg"
GMX_LOGO_URL = "https://logo.ui-portal.de/td/ab166bef-b456-4e67-984f-72fb64d4a2c6/bo10.svg"
USER_AGENT = "Mozilla/5.0 (compatible; trustedDialog-Preview-Builder/1.0)"
PREVIEW_SIZE = (1088, 464)


@st.cache_data(show_spinner=False)
def remote_data_uri(url):
    try:
        request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(request, timeout=8) as response:
            data = response.read()
            content_type = response.headers.get_content_type() or "image/svg+xml"
        return f"data:{content_type};base64," + base64.b64encode(data).decode()
    except Exception:
        return url


SEAL = remote_data_uri(SEAL_URL)
GMX_LOGO = remote_data_uri(GMX_LOGO_URL)


def upload_data_uri(upload):
    if not upload:
        return ""
    mime = "image/svg+xml" if upload.name.lower().endswith(".svg") else (upload.type or "image/png")
    return f"data:{mime};base64," + base64.b64encode(upload.getvalue()).decode()


def escape(value):
    return html.escape(value or "", quote=True)


def display_text(value):
    return escape(value[:34] + "..." if len(value) > 34 else value)


def normalize_domain(value):
    value = (value or "").strip()
    if value and not value.startswith(("http://", "https://")):
        value = "https://" + value
    return value


def is_public_url(value):
    try:
        parsed = urlparse(value)
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            return False
        for answer in socket.getaddrinfo(parsed.hostname, parsed.port or 443, type=socket.SOCK_STREAM):
            ip = ipaddress.ip_address(answer[4][0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
                return False
        return True
    except Exception:
        return False


def safe_fetch(value, max_bytes=7_000_000):
    if not is_public_url(value):
        raise ValueError("Die Domain ist nicht öffentlich erreichbar oder wurde aus Sicherheitsgründen blockiert.")
    with requests.get(value, headers={"User-Agent": USER_AGENT}, timeout=12, stream=True, allow_redirects=True) as response:
        response.raise_for_status()
        if not is_public_url(response.url):
            raise ValueError("Die Weiterleitung wurde blockiert.")
        data = bytearray()
        for chunk in response.iter_content(65_536):
            data.extend(chunk)
            if len(data) > max_bytes:
                raise ValueError("Die abgerufene Datei ist zu groß.")
        return bytes(data), response.url, response.headers.get("content-type", "")


def metadata(soup, *keys):
    for key in keys:
        node = soup.find("meta", attrs={"property": key}) or soup.find("meta", attrs={"name": key})
        if node and node.get("content"):
            return node["content"].strip()
    return ""


def unique(values):
    result, seen = [], set()
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def shorten(value, limit=37):
    value = re.sub(r"\s+", " ", value or "").strip()
    return value if len(value) <= limit else value[: limit - 3].rstrip() + "..."


def analyze_site(domain):
    raw, final_url, _ = safe_fetch(normalize_domain(domain), 3_000_000)
    soup = BeautifulSoup(raw, "html.parser")
    title = metadata(soup, "og:site_name") or (soup.title.get_text(" ", strip=True) if soup.title else "")
    host = (urlparse(final_url).hostname or "").replace("www.", "")
    brand = re.split(r"\s*[|–—]\s*", title)[0].strip() if title else host.split(".")[0]
    brand = re.sub(r"\s+-\s+.*$", "", brand).strip() or host
    description = metadata(soup, "og:description", "description")
    body_text = " ".join(soup.stripped_strings)

    offers = []
    patterns = [
        r"\b\d{1,2}\s?%\s*(?:Rabatt|sparen|off)?\b",
        r"\b\d+(?:[,.]\d{1,2})?\s?€\s*(?:Rabatt|Gutschein|sparen)?\b",
        r"\b(?:Willkommensrabatt|Gratis Versand|kostenloser Versand|Sale|Gutschein|Rabatt)\b[^.!?]{0,65}",
    ]
    for pattern in patterns:
        offers.extend(re.findall(pattern, body_text, flags=re.I))
    offers = unique([re.sub(r"\s+", " ", item).strip(" -|") for item in offers])[:8]

    colors = []
    theme = metadata(soup, "theme-color")
    if theme:
        colors.append(theme)
    colors.extend(re.findall(r"#[0-9a-fA-F]{6}\b", str(soup)[:350_000]))
    colors = unique(colors)[:12]

    image_candidates, logos = [], []
    social_image = metadata(soup, "og:image", "twitter:image")
    if social_image:
        image_candidates.append((10, urljoin(final_url, social_image)))

    for tag in soup.find_all("img"):
        src = tag.get("src") or tag.get("data-src") or tag.get("data-lazy-src")
        if not src:
            continue
        src = urljoin(final_url, src)
        marker = (" ".join(tag.get("class", [])) + " " + tag.get("id", "") + " " + tag.get("alt", "")).lower()
        if "logo" in marker:
            logos.append(src)
            continue
        if src.lower().split("?")[0].endswith((".svg", ".gif")):
            continue
        score = 0
        if any(word in marker for word in ("hero", "banner", "stage", "campaign", "teaser")):
            score += 5
        try:
            width = int(str(tag.get("width", "0")).replace("px", ""))
            height = int(str(tag.get("height", "0")).replace("px", ""))
            if width >= 600:
                score += 3
            if width and height and width / height > 1.5:
                score += 2
        except Exception:
            pass
        image_candidates.append((score, src))

    for link in soup.find_all("link"):
        rel = " ".join(link.get("rel", [])).lower()
        if any(word in rel for word in ("icon", "apple-touch-icon")) and link.get("href"):
            logos.append(urljoin(final_url, link["href"]))

    images = unique([url for _, url in sorted(image_candidates, key=lambda item: item[0], reverse=True)])[:10]
    logos = unique(logos)[:8]
    offer = offers[0] if offers else ""
    if offer:
        subject = shorten(("Jetzt " + offer + " sichern") if len(offer) < 26 else offer)
        preheader = "Angebot jetzt entdecken"
    else:
        subject = shorten("Neuigkeiten von " + brand)
        preheader = "Jetzt Vorteile entdecken"

    return {
        "url": final_url,
        "brand": shorten(brand),
        "description": description,
        "offers": offers,
        "colors": colors,
        "images": images,
        "logos": logos,
        "subject": subject,
        "preheader": shorten(preheader),
    }


def image_from_url(url):
    raw, _, _ = safe_fetch(url, 9_000_000)
    image = Image.open(io.BytesIO(raw))
    image.load()
    return image.convert("RGB")


def font(size, bold=False):
    """Cloud-safe scalable font. Pillow 10.1+ supports a sized embedded fallback."""
    paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ]
    for path in paths:
        try:
            return ImageFont.truetype(path, int(size))
        except OSError:
            pass
    try:
        return ImageFont.load_default(size=int(size))
    except TypeError:
        return ImageFont.load_default()


def readable_color(rgb):
    luminance = 0.2126 * (rgb[0] / 255) + 0.7152 * (rgb[1] / 255) + 0.0722 * (rgb[2] / 255)
    return (17, 17, 17) if luminance > 0.56 else (255, 255, 255)


def safe_brand_rgb(value):
    try:
        rgb = ImageColor.getrgb(value)
        return rgb[:3]
    except Exception:
        return (19, 117, 215)


def campaign_message(headline):
    text = re.sub(r"\s+", " ", headline or "").strip()
    percent = re.search(r"(?<!\d)(\d{1,2})\s?%", text)
    euro = re.search(r"(?<!\d)(\d+(?:[,.]\d{1,2})?)\s?€", text)
    urgent = next((word for word in ("Nur heute", "Letzte Chance", "Endet morgen") if word.lower() in text.lower()), "")
    if percent:
        return urgent.upper() if urgent else "BIS ZU", percent.group(1) + " %", "SPAREN", "JETZT SHOPPEN"
    if euro:
        return urgent.upper() if urgent else "JETZT", euro.group(1) + " €", "SPAREN", "ANGEBOT SICHERN"
    cleaned = re.sub(r"\b(jetzt|entdecken|sichern|shoppen|kaufen|angebot)\b", "", text, flags=re.I)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" -–—!")
    return "", " ".join(cleaned.split()[:4]).upper() or "NEU ENTDECKEN", "", "JETZT ENTDECKEN"


def fit_font(draw, text, max_width, start_size, min_size=25, bold=True):
    for size in range(start_size, min_size - 1, -2):
        candidate = font(size, bold)
        if draw.textlength(text, font=candidate) <= max_width:
            return candidate
    return font(min_size, bold)


def wrap_fitted_text(draw, text, max_width, start_size, min_size=28, max_lines=2):
    for size in range(start_size, min_size - 1, -2):
        selected = font(size, True)
        lines, line = [], ""
        for word in text.split():
            test = (line + " " + word).strip()
            if draw.textlength(test, font=selected) <= max_width:
                line = test
            else:
                if line:
                    lines.append(line)
                line = word
        if line:
            lines.append(line)
        if len(lines) <= max_lines:
            return lines, selected
    return lines[:max_lines], font(min_size, True)


def generate_preview(source, headline, brand_color="#1375d7", brand_name=""):
    width, height = PREVIEW_SIZE
    result = Image.new("RGB", PREVIEW_SIZE, "white")
    brand = safe_brand_rgb(brand_color)
    if sum(brand) < 105:
        brand = tuple(min(255, value + 55) for value in brand)
    if sum(brand) > 700:
        brand = tuple(int(value * 0.68) for value in brand)

    artwork = ImageOps.fit(source.convert("RGB"), (710, height), Image.Resampling.LANCZOS, centering=(0.5, 0.5))
    result.paste(artwork, (378, 0))
    draw = ImageDraw.Draw(result)
    draw.polygon([(0, 0), (640, 0), (520, height), (0, height)], fill=brand)
    primary = readable_color(brand)

    brand_label = shorten(brand_name or "", 22)
    if brand_label:
        brand_font = fit_font(draw, brand_label, 420, 58, 34, True)
        draw.text((62, 38), brand_label, font=brand_font, fill=primary)

    upper, main, lower, cta = campaign_message(headline)
    x = 64
    if re.search(r"\d", main):
        draw.text((x, 142), upper, font=font(35, True), fill=primary)
        main_font = fit_font(draw, main, 405, 126, 78, True)
        draw.text((x, 180), main, font=main_font, fill=primary)
        lower_font = fit_font(draw, lower, 405, 54, 38, True)
        draw.text((x, 306), lower, font=lower_font, fill=primary)
    else:
        lines, main_font = wrap_fitted_text(draw, main, 400, 65, 38, 2)
        y = 158
        for line in lines:
            draw.text((x, y), line, font=main_font, fill=primary)
            y += getattr(main_font, "size", 45) + 7

    cta_label = cta + "  →"
    cta_font = fit_font(draw, cta_label, 340, 29, 24, True)
    text_width = draw.textlength(cta_label, font=cta_font)
    button_width, button_y, button_height = min(390, text_width + 62), height - 82, 58
    button_fill = (255, 255, 255) if primary == (255, 255, 255) else (17, 17, 17)
    button_text = brand if primary == (255, 255, 255) else (255, 255, 255)
    draw.rounded_rectangle((x, button_y, x + button_width, button_y + button_height), radius=29, fill=button_fill)
    draw.text((x + 31, button_y + 13), cta_label, font=cta_font, fill=button_text)
    return result


def png_bytes(image):
    buffer = io.BytesIO()
    image.save(buffer, "PNG", optimize=False)
    return buffer.getvalue()


DEFAULTS = {
    "domain": "",
    "sender": "Absender",
    "subject": "Betreff",
    "preheader": "Preview-Text",
    "color": "#b8ddfd",
    "analysis": None,
    "generated_preview": None,
    "generated_avatar": "",
    "selected_image": "",
    "brand_color": "#1375d7",
}
for key, value in DEFAULTS.items():
    st.session_state.setdefault(key, value)

st.title("trustedDialog Preview Builder")
st.caption("Domain eingeben, Vorschläge automatisch erstellen und anschließend direkt bearbeiten.")
st.subheader("1. Unternehmen analysieren")
domain_col, button_col = st.columns([4, 1])
with domain_col:
    st.text_input("Für welche Domain soll das trustedDialog Preview generiert werden?", key="domain", placeholder="z. B. www.beispiel.de")
with button_col:
    st.write("")
    st.write("")
    analyze_clicked = st.button("Vorschläge erstellen", type="primary", use_container_width=True)

if analyze_clicked:
    try:
        with st.spinner("Website wird analysiert und die Preview vorbereitet …"):
            result = analyze_site(st.session_state.domain)
            st.session_state.analysis = result
            st.session_state.sender = result["brand"]
            st.session_state.subject = result["subject"]
            st.session_state.preheader = result["preheader"]
            st.session_state.brand_color = result["colors"][0] if result["colors"] else "#1375d7"
            selected = None
            for candidate in result["images"]:
                try:
                    selected = image_from_url(candidate)
                    st.session_state.selected_image = candidate
                    break
                except Exception:
                    continue
            st.session_state.generated_preview = (
                png_bytes(generate_preview(selected, result["subject"], st.session_state.brand_color, result["brand"]))
                if selected is not None else None
            )
            st.session_state.generated_avatar = ""
            for logo in result["logos"]:
                try:
                    raw, _, content_type = safe_fetch(logo, 3_000_000)
                    st.session_state.generated_avatar = f"data:{content_type or 'image/png'};base64," + base64.b64encode(raw).decode()
                    break
                except Exception:
                    continue
        st.success("Vorschläge wurden erstellt. Alle Inhalte können unten überschrieben werden.")
    except Exception as error:
        st.error(f"Die Website konnte nicht analysiert werden: {error}")

analysis = st.session_state.analysis
if analysis:
    with st.expander("Erkannte Website-Informationen", expanded=False):
        st.write(f"**Marke:** {analysis['brand']}")
        if analysis["offers"]:
            st.write("**Gefundene Angebots-Hinweise:** " + " · ".join(analysis["offers"][:5]))
        if analysis["description"]:
            st.write("**Beschreibung:** " + analysis["description"][:350])
    if analysis["images"]:
        options = analysis["images"]
        selected_index = options.index(st.session_state.selected_image) if st.session_state.selected_image in options else 0
        selected_url = st.selectbox("Alternatives Website-Motiv", options, index=selected_index, format_func=lambda value: value.split("/")[-1][:70] or value)
        if st.button("Ausgewähltes Motiv übernehmen"):
            try:
                selected_image = image_from_url(selected_url)
                st.session_state.selected_image = selected_url
                st.session_state.generated_preview = png_bytes(
                    generate_preview(selected_image, st.session_state.subject, st.session_state.brand_color, st.session_state.sender)
                )
                st.rerun()
            except Exception as error:
                st.error(f"Das Bild konnte nicht übernommen werden: {error}")

st.subheader("2. Inhalte bearbeiten")
left, right = st.columns([0.86, 1.14], gap="large")
with left:
    st.text_input("Absender / Marke", key="sender", max_chars=37)
    st.text_input("Betreff", key="subject", max_chars=37)
    st.text_input("Preview-Text", key="preheader", max_chars=37)
    st.color_picker("Fallback-Avatarfarbe", key="color")
    avatar_upload = st.file_uploader("Avatar / Logo überschreiben", type=["svg", "png", "jpg", "jpeg", "webp"], help="SVG wird direkt nach dem Upload im Browser in PNG konvertiert und anschließend nur noch als PNG verwendet.")
    preview_upload = st.file_uploader("Preview-Bild überschreiben (1088 × 464 px)", type=["png", "jpg", "jpeg", "webp"])
    if st.session_state.generated_preview:
        filename_sender = re.sub(r"[^A-Za-z0-9._-]+", "_", st.session_state.sender)
        st.download_button("Generiertes Preview-Bild herunterladen", st.session_state.generated_preview, file_name=f"trustedDialog_Preview_{filename_sender}_1088x464.png", mime="image/png", use_container_width=True)

sender = display_text(st.session_state.sender)
subject = display_text(st.session_state.subject)
preheader = display_text(st.session_state.preheader)
download_sender = json.dumps(st.session_state.sender or "Absender", ensure_ascii=False)
avatar_src = upload_data_uri(avatar_upload) if avatar_upload else st.session_state.generated_avatar
preview_src = upload_data_uri(preview_upload) if preview_upload else ("data:image/png;base64," + base64.b64encode(st.session_state.generated_preview).decode() if st.session_state.generated_preview else "")
initials = escape("".join(word[0] for word in st.session_state.sender.split()[:2]).upper() or "M")
avatar_html = f'<img class="avatar" id="uploaded-avatar" data-is-svg="{str(bool(avatar_upload and avatar_upload.name.lower().endswith(".svg"))).lower()}" src="{avatar_src}">' if avatar_src else f'<span class="avatar fallback" style="background:#b8ddfd;color:#1375d7">{initials}</span>'
preview_html = f'<img class="preview" src="{preview_src}">' if preview_src else '<div class="preview placeholder">Bild einfügen</div>'
seal_html = f'<img class="seal" src="{SEAL}" alt="trustedDialog Siegel">'

mockup_html = f'''<!doctype html><html><head><meta charset="utf-8"><script src="https://cdn.jsdelivr.net/npm/html2canvas@1.4.1/dist/html2canvas.min.js"></script><style>
*{{box-sizing:border-box}}html,body{{margin:0;background:transparent;font-family:Arial,sans-serif}}.stage{{display:flex;flex-direction:column;align-items:center}}.phone{{position:relative;width:390px;height:780px;border-radius:58px;background:#111;border:2px solid #777;box-shadow:inset 0 0 0 2px #d4d4d4,0 8px 22px #0003}}.phone:before{{content:"";position:absolute;inset:5px;border:1px solid #333;border-radius:53px;z-index:9;pointer-events:none}}.screen{{position:absolute;inset:14px;width:362px;height:752px;overflow:hidden;border-radius:46px;background:#fff;color:#111}}.status{{position:relative;height:43px;padding:13px 23px 0;font-size:14px;font-weight:700}}.island{{position:absolute;top:9px;left:50%;transform:translateX(-50%);width:106px;height:31px;border-radius:18px;background:#090909}}.sright{{position:absolute;right:19px;top:10px;height:23px;display:flex;align-items:center;gap:8px}}.signal{{display:flex;align-items:flex-end;gap:2px;height:15px}}.signal i{{width:4px;background:#111;border-radius:2px}}.signal i:nth-child(1){{height:6px}}.signal i:nth-child(2){{height:9px}}.signal i:nth-child(3){{height:12px}}.signal i:nth-child(4){{height:15px}}.wifi-icon{{width:21px;height:18px;display:block;fill:#111}}.battery{{height:21px;min-width:34px;padding:0 5px;border-radius:7px;background:#111;color:#fff;display:flex;align-items:center;justify-content:center;font-size:12px}}.hdr{{height:60px;display:grid;grid-template-columns:38px 1fr 40px 40px;align-items:center;gap:5px;padding:0 14px}}.round{{width:36px;height:36px;border-radius:50%;background:#fafafa;display:flex;align-items:center;justify-content:center}}.back{{font-size:28px}}.head strong{{display:block;font-size:14px;line-height:17px}}.head small{{display:block;font-size:10px;color:#aaa}}.hicon{{width:21px;height:21px;stroke:#111;fill:none;stroke-width:2.2;stroke-linecap:round;stroke-linejoin:round}}.search{{height:42px;margin:0 17px 12px;border-radius:22px;background:#f4f4f5;display:flex;align-items:center;padding:0 16px;color:#777;font-size:15px}}.receive{{height:34px;border-top:1px solid #ddd;border-bottom:1px solid #ddd;padding:0 17px;display:flex;align-items:center;gap:14px;color:#777;font-size:11px}}.dots{{color:#5caee9;letter-spacing:3px;font-size:16px}}.list{{margin:0 17px}}.row{{display:grid;grid-template-columns:42px minmax(0,1fr) 42px;column-gap:10px;border-bottom:1px solid #ddd;padding:10px 0 9px}}.row.td{{min-height:194px;padding-top:11px}}.avatar{{width:38px;height:38px;border-radius:50%;object-fit:cover;display:flex;align-items:center;justify-content:center;color:#fff;font-size:13px;font-weight:700}}.avatar.fallback{{color:#1375d7}}.content{{min-width:0}}.senderline{{height:18px;display:flex;align-items:center;white-space:nowrap}}.sender{{font-size:13px;line-height:18px;font-weight:700;max-width:166px;overflow:hidden;text-overflow:ellipsis}}.seal{{width:16px;height:16px;flex:0 0 16px;margin-left:4px;object-fit:contain}}.subject,.pre{{height:18px;font-size:13px;line-height:18px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}.pre{{color:#aaa}}.time{{grid-column:3;grid-row:1;text-align:right;color:#aaa;font-size:10px;padding-top:2px}}.pwrap{{grid-column:2/4;margin-top:3px;width:253px;height:96px;border-radius:6px;overflow:hidden}}.preview{{width:100%;height:100%;object-fit:cover}}.placeholder{{background:#ff00e8;color:#fff;display:flex;align-items:center;justify-content:center;font-size:11px}}.standard{{min-height:78px}}.standard .sender{{max-width:185px}}.standard .subject,.standard .pre{{max-width:218px}}.nav{{position:absolute;left:14px;right:14px;bottom:14px;height:67px;display:grid;grid-template-columns:repeat(5,1fr);padding:5px 7px;border-radius:35px;background:#fff;box-shadow:0 1px 18px #0002}}.navitem{{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:2px;border-radius:29px;font-size:11px;font-weight:600}}.navitem.active{{background:#ededed;color:#1873bf}}.nsvg{{width:29px;height:29px;fill:#111;stroke:#111}}.active .nsvg{{fill:#1873bf;stroke:#1873bf}}.home{{position:absolute;left:50%;bottom:5px;transform:translateX(-50%);width:125px;height:4px;border-radius:3px;background:#111}}.downloadbar{{margin-top:12px;text-align:center}}.downloadbtn{{border:1px solid #777;background:#fff;color:#111;border-radius:6px;padding:9px 14px;font:600 13px Arial,sans-serif;cursor:pointer}}
</style></head><body><div class="stage"><div class="phone"><div class="screen"><div class="status"><span id="now">09:24</span><span class="island"></span><span class="sright"><span class="signal"><i></i><i></i><i></i><i></i></span><svg class="wifi-icon" viewBox="0 0 24 18"><path d="M2 6.2C7.6 1.6 16.4 1.6 22 6.2L19.3 9C15.2 5.7 8.8 5.7 4.7 9L2 6.2Z"/><path d="M6.2 10.5C9.5 7.8 14.5 7.8 17.8 10.5L15.1 13.2C13.3 11.8 10.7 11.8 8.9 13.2L6.2 10.5Z"/><path d="M9.9 14.5C11.1 13.5 12.9 13.5 14.1 14.5L12 17L9.9 14.5Z"/></svg><span class="battery">93</span></span></div><div class="hdr"><span class="round back">‹</span><span class="head"><strong>Posteingang</strong><small>trusteddialog01@gmx.net</small></span><span class="round">✓</span><span class="round">✎</span></div><div class="search">⌕ &nbsp; Suchen</div><div class="receive"><span class="dots">•••</span>E-Mails empfangen</div><div class="list">
<div class="row td"><div>{avatar_html}</div><div class="content"><div class="senderline"><span class="sender">{sender}</span>{seal_html}</div><div class="subject">{subject}</div><div class="pre">{preheader}</div></div><div class="time" data-off="-3"></div><div class="pwrap">{preview_html}</div></div>
<div class="row standard"><div><span class="avatar fallback" style="background:#b8ddfd;color:#1375d7">OH</span></div><div class="content"><div class="senderline"><span class="sender">Otto Holler</span></div><div class="subject">Gewünschte Bilder</div><div class="pre">Hallo zusammen, anbei findet Ihr die…</div></div><div class="time" data-off="-15"></div></div>
<div class="row standard"><div><img class="avatar" src="{GMX_LOGO}"></div><div class="content"><div class="senderline"><span class="sender">GMX Magazin</span>{seal_html}</div><div class="subject">Traumhaus auf Föhr zu gewinnen: 8…</div><div class="pre">Jetzt Lose bei GMX Lotto sichern! W…</div></div><div class="time" data-off="-34"></div></div>
<div class="row standard"><div><span class="avatar fallback" style="background:#b8ddfd;color:#1375d7">SW</span></div><div class="content"><div class="senderline"><span class="sender">Shopping World</span></div><div class="subject">Neue Deals am Wochenende</div><div class="pre">Jetzt entdecken</div></div><div class="time" data-off="-47"></div></div>
<div class="row standard" style="border:0"><div><span class="avatar fallback" style="background:#b8ddfd;color:#1375d7">FF</span></div><div class="content"><div class="senderline"><span class="sender">Fred Fritt</span></div><div class="subject">Klassentreffen</div><div class="pre">Hallo zusammen, vielen Dank für das to…</div></div><div class="time" data-off="-59"></div></div></div>
<div class="nav"><div class="navitem active">✉<br>E-Mail</div><div class="navitem">■<br>Dateien</div><div class="navitem">▣<br>Fotos</div><div class="navitem">▥<br>Mobil</div><div class="navitem">▤<br>News</div></div><div class="home"></div></div></div><div class="downloadbar"><button class="downloadbtn" onclick="downloadPreview()">GMX-Vorschau als PNG herunterladen</button></div></div>
<script>
const p=n=>String(n).padStart(2,'0'),fmt=d=>p(d.getHours())+':'+p(d.getMinutes());function tick(){{const n=new Date();document.getElementById('now').textContent=fmt(n);document.querySelectorAll('[data-off]').forEach(x=>x.textContent=fmt(new Date(n.getTime()+Number(x.dataset.off)*60000)))}}tick();setInterval(tick,30000);
async function svgAvatarToPngImmediately(){{const img=document.getElementById('uploaded-avatar');if(!img||img.dataset.isSvg!=='true')return;await new Promise(r=>{{if(img.complete)r();else{{img.onload=r;img.onerror=r}}}});const source=new Image();await new Promise((r,j)=>{{source.onload=r;source.onerror=j;source.src=img.currentSrc||img.src}});const size=256,canvas=document.createElement('canvas');canvas.width=size;canvas.height=size;const ctx=canvas.getContext('2d'),sw=source.naturalWidth||size,sh=source.naturalHeight||size,scale=Math.max(size/sw,size/sh),dw=sw*scale,dh=sh*scale;ctx.drawImage(source,(size-dw)/2,(size-dh)/2,dw,dh);img.src=canvas.toDataURL('image/png');img.removeAttribute('data-is-svg')}}svgAvatarToPngImmediately().catch(console.warn);
async function downloadPreview(){{const button=document.querySelector('.downloadbtn'),phone=document.querySelector('.phone'),original=button.textContent;try{{button.disabled=true;button.textContent='PNG wird erstellt…';await document.fonts.ready;await Promise.all(Array.from(phone.querySelectorAll('img')).map(i=>i.complete?Promise.resolve():new Promise(r=>{{i.onload=r;i.onerror=r}})));const canvas=await html2canvas(phone,{{backgroundColor:null,scale:2,useCORS:true,allowTaint:false,logging:false,width:390,height:780,onclone:(doc)=>{{doc.querySelectorAll('img.preview').forEach(img=>{{const wrap=img.closest('.pwrap');if(wrap){{wrap.style.backgroundImage='url("'+img.src+'")';wrap.style.backgroundSize='cover';wrap.style.backgroundPosition='center';img.style.visibility='hidden'}}}})}}}});const safe=String({download_sender}).trim().replace(/[\\/:*?"<>|]+/g,'_')||'Absender',blob=await new Promise(r=>canvas.toBlob(r,'image/png')),url=URL.createObjectURL(blob),link=document.createElement('a');link.download='GMX_trustedDialogPreview_'+safe+'.png';link.href=url;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}}catch(error){{alert('Die PNG-Datei konnte nicht erzeugt werden: '+error.message)}}finally{{button.disabled=false;button.textContent=original}}}}
</script></body></html>'''

with right:
    st.subheader("3. GMX Live-Vorschau")
    st.caption("Smartphone · GMX.DE · iOS")
    components.html(mockup_html, height=860, scrolling=False)
