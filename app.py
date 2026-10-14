import base64, colorsys, html, io, ipaddress, json, math, os, re, socket
from functools import lru_cache
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen
import requests
from bs4 import BeautifulSoup
from PIL import Image, ImageColor, ImageDraw, ImageFilter, ImageFont, ImageOps
import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title='trustedDialog Preview Builder', page_icon='✉️', layout='wide')

SEAL_URL = 'https://img.ui-portal.de/trusteddialog/trustlogo/trusted-sign_GMX.svg'
GMX_LOGO_URL = 'https://logo.ui-portal.de/td/ab166bef-b456-4e67-984f-72fb64d4a2c6/bo10.svg'
UA = 'Mozilla/5.0 (compatible; trustedDialog-Preview-Builder/1.0)'
PREVIEW_SIZE = (1088, 464)
AVATAR_DEFAULT = '#8ea8ce'  # Platzhalter-Avatar laut GMX-Vorlage


@st.cache_data(show_spinner=False)
def remote_data_uri(url):
    try:
        req = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urlopen(req, timeout=8) as response:
            data = response.read()
            content_type = response.headers.get_content_type() or 'image/svg+xml'
        return f'data:{content_type};base64,' + base64.b64encode(data).decode()
    except Exception:
        return url


def uri(f):
    if not f:
        return ''
    mime = 'image/svg+xml' if f.name.lower().endswith('.svg') else (f.type or 'image/png')
    return f'data:{mime};base64,' + base64.b64encode(f.getvalue()).decode()


def e(x):
    return html.escape(x or '', quote=True)


def display_text(x):
    return e(x[:34] + '...' if len(x) > 34 else x)


# ---------------------------------------------------------------------------
# Website-Analyse
# ---------------------------------------------------------------------------
def normalize_domain(value):
    value = (value or '').strip()
    if value and not value.startswith(('http://', 'https://')):
        value = 'https://' + value
    return value


def public_url(value):
    try:
        parsed = urlparse(value)
        if parsed.scheme not in ('http', 'https') or not parsed.hostname:
            return False
        for answer in socket.getaddrinfo(parsed.hostname, parsed.port or 443, type=socket.SOCK_STREAM):
            ip = ipaddress.ip_address(answer[4][0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
                return False
        return True
    except Exception:
        return False


def safe_fetch(value, max_bytes=7000000):
    if not public_url(value):
        raise ValueError('Die Domain ist nicht öffentlich erreichbar oder wurde aus Sicherheitsgründen blockiert.')
    with requests.get(value, headers={'User-Agent': UA}, timeout=12, stream=True, allow_redirects=True) as response:
        response.raise_for_status()
        if not public_url(response.url):
            raise ValueError('Die Weiterleitung wurde blockiert.')
        data = bytearray()
        for chunk in response.iter_content(65536):
            data.extend(chunk)
            if len(data) > max_bytes:
                raise ValueError('Die abgerufene Datei ist zu groß.')
        return bytes(data), response.url, response.headers.get('content-type', '')


def meta(soup, *keys):
    for key in keys:
        node = soup.find('meta', attrs={'property': key}) or soup.find('meta', attrs={'name': key})
        if node and node.get('content'):
            return node['content'].strip()
    return ''


def unique(values):
    out = []
    seen = set()
    for value in values:
        if value and value not in seen:
            seen.add(value)
            out.append(value)
    return out


def short(value, limit=37):
    value = re.sub(r'\s+', ' ', value or '').strip()
    return value if len(value) <= limit else value[:limit - 3].rstrip() + '...'


# ---------------------------------------------------------------------------
# Farben: Kontrast und Marken-/CI-Farberkennung
# ---------------------------------------------------------------------------
HEX_RE = re.compile(r'#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})(?![0-9a-zA-Z])')
RGB_RE = re.compile(r'rgba?\(\s*(\d{1,3})\s*[, ]\s*(\d{1,3})\s*[, ]\s*(\d{1,3})')
CSS_VAR_RE = re.compile(
    r'--[\w-]*(?:primary|brand|accent|cta|highlight|key|main)[\w-]*\s*:\s*(#[0-9a-fA-F]{3,6}\b|rgba?\([^)]+\))', re.I)


def rgb_to_hex(rgb):
    return '#%02x%02x%02x' % tuple(int(max(0, min(255, v))) for v in rgb[:3])


def parse_color(raw):
    """CSS-Farbe (#abc, #aabbcc, rgb(...)) -> (r, g, b) oder None."""
    raw = (raw or '').strip()
    m = HEX_RE.fullmatch(raw)
    if m:
        h = m.group(1)
        if len(h) == 3:
            h = ''.join(c * 2 for c in h)
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    m = RGB_RE.match(raw)
    if m:
        return tuple(min(255, int(v)) for v in m.groups())
    return None


def safe_brand_rgb(value):
    try:
        rgb = ImageColor.getrgb(value)
        return tuple(rgb[:3])
    except Exception:
        return (19, 117, 215)


def rel_lum(rgb):
    def channel(v):
        v /= 255
        return v / 12.92 if v <= .03928 else ((v + .055) / 1.055) ** 2.4
    r, g, b = [channel(v) for v in rgb[:3]]
    return .2126 * r + .7152 * g + .0722 * b


def contrast(a, b):
    la, lb = rel_lum(a), rel_lum(b)
    return (max(la, lb) + .05) / (min(la, lb) + .05)


def hsv(rgb):
    return colorsys.rgb_to_hsv(*[v / 255 for v in rgb[:3]])


def usable_brand_color(rgb):
    """Graue, fast weiße und fast schwarze Töne sind keine Markenfarben."""
    _, s, v = hsv(rgb)
    return s >= .28 and v >= .18 and .015 <= rel_lum(rgb) <= .85


def page_color_scores(soup, html_text):
    """Sammelt Farbkandidaten der Seite: theme-color, CSS-Variablen, Häufigkeit im Quelltext."""
    scores = {}

    def add(raw, weight):
        rgb = parse_color(raw)
        if rgb and usable_brand_color(rgb):
            key = rgb_to_hex(rgb)
            scores[key] = scores.get(key, 0) + weight

    add(meta(soup, 'theme-color', 'msapplication-TileColor'), 9)
    for match in CSS_VAR_RE.findall(html_text[:500000]):
        add(match, 5)
    counts = {}
    source = html_text[:500000]
    for match in HEX_RE.finditer(source):
        counts[match.group(0)] = counts.get(match.group(0), 0) + 1
    for match in RGB_RE.finditer(source):
        key = 'rgb(%s,%s,%s)' % match.groups()
        counts[key] = counts.get(key, 0) + 1
    for raw, count in counts.items():
        add(raw, count ** .7)
    return scores


def dominant_logo_color(logo):
    """Häufigste gesättigte Farbe eines Logos (beste Quelle für die CI-Farbe)."""
    if logo is None:
        return None
    small = logo.convert('RGBA')
    small.thumbnail((96, 96))
    buckets = {}
    for r, g, b, a in small.getdata():
        if a < 200:
            continue
        _, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
        if s < .3 or v < .2:
            continue
        key = (r // 24, g // 24, b // 24)
        n, sr, sg, sb = buckets.get(key, (0, 0, 0, 0))
        buckets[key] = (n + 1, sr + r, sg + g, sb + b)
    if not buckets:
        return None
    n, sr, sg, sb = max(buckets.values(), key=lambda item: item[0])
    return (sr // n, sg // n, sb // n)


def rank_brand_colors(scores, logo=None):
    scores = dict(scores)
    logo_rgb = dominant_logo_color(logo)
    if logo_rgb and usable_brand_color(logo_rgb):
        key = rgb_to_hex(logo_rgb)
        scores[key] = scores.get(key, 0) + 30
    ranked = []
    for key, score in sorted(scores.items(), key=lambda item: item[1] * (.5 + hsv(parse_color(item[0]))[1]), reverse=True):
        rgb = parse_color(key)
        for index, (leader, total) in enumerate(ranked):
            lead = parse_color(leader)
            if sum((a - b) ** 2 for a, b in zip(rgb, lead)) ** .5 < 38:
                ranked[index] = (leader, total + score)  # ähnliche Töne zusammenfassen
                break
        else:
            ranked.append((key, score))
    ranked.sort(key=lambda item: item[1], reverse=True)
    return [key for key, _ in ranked][:8]


def analyze_site(value):
    raw, final_url, content_type = safe_fetch(normalize_domain(value), 3000000)
    html_text = raw.decode('utf-8', errors='ignore')
    soup = BeautifulSoup(raw, 'html.parser')
    title = meta(soup, 'og:site_name') or (soup.title.get_text(' ', strip=True) if soup.title else '')
    host = (urlparse(final_url).hostname or '').replace('www.', '')
    brand = re.split(r'\s*[|–—]\s*', title)[0].strip() if title else host.split('.')[0]
    brand = re.sub(r'\s+-\s+.*$', '', brand).strip() or host
    description = meta(soup, 'og:description', 'description')
    body_text = ' '.join(soup.stripped_strings)
    offers = []
    patterns = [r'\b\d{1,2}\s?%\s*(?:Rabatt|sparen|off)?\b',
                r'\b\d+(?:[,.]\d{1,2})?\s?€\s*(?:Rabatt|Gutschein|sparen)?\b',
                r'\b(?:Willkommensrabatt|Gratis Versand|kostenloser Versand|Sale|Gutschein|Rabatt)\b[^.!?]{0,65}']
    for pattern in patterns:
        offers.extend(re.findall(pattern, body_text, flags=re.I))
    offers = unique([re.sub(r'\s+', ' ', x).strip(' -|') for x in offers])[:8]
    color_scores = page_color_scores(soup, html_text)
    images = []
    logos = []
    og = meta(soup, 'og:image', 'twitter:image')
    if og:
        images.append((6, urljoin(final_url, og)))
    for tag in soup.find_all('img'):
        src = tag.get('src') or tag.get('data-src') or tag.get('data-lazy-src')
        if not src:
            continue
        src = urljoin(final_url, src)
        marker = (' '.join(tag.get('class', [])) + ' ' + (tag.get('id') or '') + ' ' + (tag.get('alt') or '')).lower()
        if 'logo' in marker:
            logos.append(src)
        elif not src.lower().split('?')[0].endswith(('.svg', '.gif')):
            score = 0
            if any(word in marker for word in ('hero', 'banner', 'stage', 'campaign', 'teaser')):
                score += 5
            try:
                width = int(str(tag.get('width', '0')).replace('px', ''))
                height = int(str(tag.get('height', '0')).replace('px', ''))
                if width >= 600:
                    score += 3
                if width and height and width / height > 1.5:
                    score += 2
            except Exception:
                pass
            images.append((score, src))
    for link in soup.find_all('link'):
        rel = ' '.join(link.get('rel', [])).lower()
        if any(x in rel for x in ('icon', 'apple-touch-icon')) and link.get('href'):
            logos.append(urljoin(final_url, link['href']))
    images = unique([x[1] for x in sorted(images, key=lambda item: item[0], reverse=True)])[:10]
    logos = unique(logos)[:8]
    offer = offers[0] if offers else ''
    if offer:
        subject = short(('Jetzt ' + offer + ' sichern') if len(offer) < 26 else offer)
        preheader = short('Angebot jetzt entdecken')
    else:
        subject = short('Neuigkeiten von ' + brand)
        preheader = short('Jetzt Vorteile entdecken')
    return {'url': final_url, 'brand': short(brand), 'description': description, 'offers': offers,
            'color_scores': color_scores, 'colors': rank_brand_colors(color_scores), 'images': images,
            'logos': logos, 'subject': subject, 'preheader': preheader}


# ---------------------------------------------------------------------------
# Bild-Helfer
# ---------------------------------------------------------------------------
def flatten_to_rgb(image):
    """Transparente PNGs auf Weiß legen (statt schwarzem Hintergrund)."""
    if image.mode in ('RGBA', 'LA') or (image.mode == 'P' and 'transparency' in image.info):
        rgba = image.convert('RGBA')
        base = Image.new('RGBA', rgba.size, (255, 255, 255, 255))
        base.alpha_composite(rgba)
        return base.convert('RGB')
    return image.convert('RGB')


def image_from_bytes(raw):
    image = Image.open(io.BytesIO(raw))
    image.load()
    return image


def image_from_url(value):
    raw, _, _ = safe_fetch(value, 9000000)
    return flatten_to_rgb(image_from_bytes(raw))


def to_bytes(image, fmt='PNG'):
    buffer = io.BytesIO()
    if fmt == 'JPEG':
        image.convert('RGB').save(buffer, 'JPEG', quality=93)
    else:
        image.save(buffer, 'PNG', optimize=False)
    return buffer.getvalue()


def png_data(image):
    return to_bytes(image, 'PNG')


def usable_motif(image):
    width, height = image.size
    return width >= 500 and height >= 220 and .7 <= width / height <= 4


def prepare_logo(image):
    """Logo zuschneiden; weißen Hintergrund (JPG/PNG ohne Alpha) freistellen."""
    logo = image.convert('RGBA')
    w, h = logo.size
    px = logo.load()
    corners = [px[0, 0], px[w - 1, 0], px[0, h - 1], px[w - 1, h - 1]]
    if all(c[3] > 240 and min(c[:3]) > 240 for c in corners):
        logo.putdata([(r, g, b, 0) if min(r, g, b) > 238 else (r, g, b, a) for r, g, b, a in logo.getdata()])
    bbox = logo.getchannel('A').point(lambda v: 255 if v > 20 else 0).getbbox()
    if bbox:
        logo = logo.crop(bbox)
    return logo if min(logo.size) >= 40 else None


def smart_fit(image, size):
    """Zuschnitt mit Fokus auf kontrastreiche, farbige Bildbereiche statt starrer Bildmitte."""
    small = image.convert('RGB')
    small.thumbnail((96, 96))
    edges = small.convert('L').filter(ImageFilter.FIND_EDGES).filter(ImageFilter.GaussianBlur(1.5))
    sat = small.convert('HSV').getchannel('S')
    w, h = small.size
    total = sx = sy = 0.0
    for y in range(h):
        for x in range(w):
            weight = edges.getpixel((x, y)) + .5 * sat.getpixel((x, y)) + 1
            total += weight
            sx += weight * x
            sy += weight * y
    cx, cy = (sx / total / w, sy / total / h) if total else (.5, .5)
    centering = (min(.75, max(.25, cx)), min(.75, max(.25, cy)))
    return ImageOps.fit(image.convert('RGB'), size, Image.Resampling.LANCZOS, centering=centering)


# ---------------------------------------------------------------------------
# Schriften (robuste Suche, skalierbarer Fallback)
# ---------------------------------------------------------------------------
BOLD_PREFERENCE = ['roboto-black.ttf', 'roboto-bold.ttf', 'inter-extrabold.ttf', 'inter-bold.ttf',
                   'montserrat-extrabold.ttf', 'montserrat-bold.ttf', 'opensans-bold.ttf', 'notosans-bold.ttf',
                   'liberationsans-bold.ttf', 'arialbd.ttf', 'arial bold.ttf', 'helveticaneue-bold.ttf',
                   'dejavusans-bold.ttf']


@lru_cache(maxsize=1)
def font_index():
    here = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.getcwd()
    roots = [os.path.join(here, 'fonts'), '/usr/share/fonts', '/usr/local/share/fonts', os.path.expanduser('~/.fonts'),
             os.path.expanduser('~/.local/share/fonts'), '/Library/Fonts', '/System/Library/Fonts/Supplemental',
             'C:/Windows/Fonts']
    found = {}
    for root in roots:
        for directory, _, files in os.walk(root):
            for name in files:
                if name.lower().endswith(('.ttf', '.otf')):
                    found.setdefault(name.lower(), os.path.join(directory, name))
    return found


@lru_cache(maxsize=64)
def get_font(size):
    size = max(8, int(size))
    index = font_index()
    for name in BOLD_PREFERENCE:
        if name in index:
            try:
                return ImageFont.truetype(index[name], size)
            except OSError:
                continue
    try:
        return ImageFont.load_default(size)  # Pillow >= 10.1: skalierbar
    except TypeError:
        return ImageFont.load_default()


def cap_height(font):
    return -font.getbbox('H', anchor='ls')[1]


# ---------------------------------------------------------------------------
# tD-Preview-Grafik
# ---------------------------------------------------------------------------
def campaign_message(headline):
    """Reduziert Website-Wording auf EINE dominante Botschaft + kurzen CTA (ohne Erfindungen)."""
    text = re.sub(r'\s+', ' ', headline or '').strip()
    low = text.lower()
    urgent = next((w for w in ('Nur heute', 'Letzte Chance', 'Endet morgen') if w.lower() in low), '')
    percent = re.search(r'(?<![\d,.])(\d{1,2})\s?(?:%|prozent)', text, re.I)
    euro = re.search(r'(?<![\d,.])(\d+(?:[,.]\d{1,2})?)\s?€', text)
    if percent:
        upper = 'BIS ZU' if 'bis zu' in low else (urgent.upper() if urgent else '')
        return {'upper': upper, 'main': percent.group(1) + ' %', 'lower': 'RABATT' if 'rabatt' in low else 'SICHERN',
                'cta': 'JETZT SHOPPEN', 'numeric': True}
    if re.search(r'(gratis|kostenlos\w*) versand', low):
        return {'upper': '', 'main': 'GRATIS', 'lower': 'VERSAND', 'cta': 'JETZT SHOPPEN', 'numeric': True}
    if euro:
        upper = 'AB' if re.search(r'\bab\b', low) else (urgent.upper() if urgent else '')
        lower = 'GUTSCHEIN' if 'gutschein' in low else ('RABATT' if 'rabatt' in low else '')
        return {'upper': upper, 'main': euro.group(1) + ' €', 'lower': lower, 'cta': 'ANGEBOT SICHERN', 'numeric': True}
    if re.search(r'\bsale\b', low):
        return {'upper': '', 'main': 'SALE', 'lower': '', 'cta': 'JETZT SPAREN', 'numeric': True}
    if not text or low.startswith('neuigkeiten von'):
        return {'upper': '', 'main': 'NEU ENTDECKEN', 'lower': '', 'cta': 'JETZT ENTDECKEN', 'numeric': False}
    cleaned = re.sub(r'\bjetzt\b', '', text, flags=re.I)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip(' -–—!.')
    words = cleaned.split()[:3]
    return {'upper': '', 'main': ' '.join(words).upper() or 'NEU ENTDECKEN', 'lower': '', 'cta': 'JETZT ENTDECKEN',
            'numeric': False}


def panel_colors(brand):
    """Wählt Textfarbe nach WCAG-Kontrast; dunkelt die Markenfarbe nur im Notfall ab."""
    white, ink = (255, 255, 255), (17, 17, 17)
    if contrast(brand, white) >= 3.5:      # sehr große, fette Schrift: 3:1 reicht formal, 3,5:1 wirkt klein noch lesbar
        return brand, white
    if contrast(brand, ink) >= 4.5:
        return brand, ink
    adjusted = brand
    for _ in range(30):
        adjusted = tuple(int(v * .93) for v in adjusted)
        if contrast(adjusted, white) >= 3.8:
            break
    return adjusted, white


def wrap_words(words, font, max_width):
    lines, line = [], ''
    for word in words:
        if font.getlength(word) > max_width:
            return None
        test = (line + ' ' + word).strip()
        if font.getlength(test) <= max_width:
            line = test
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def fit_message(msg, box_w, box_h, S):
    """Skaliert Text so, dass er Breite UND Höhe des Textfeldes einhält. Rückgabe: (Zeilen, Zeilenabstand)."""
    if msg['numeric']:
        for size in range(190 * S, 60 * S - 1, -4 * S):
            items, ok = [], True
            for key, ratio, minimum in (('upper', .22, 30), ('main', 1, 0), ('lower', .30, 34)):
                text = msg[key]
                if not text:
                    continue
                font = get_font(size if key == 'main' else max(int(size * ratio), minimum * S))
                if font.getlength(text) > box_w:
                    ok = False
                    break
                items.append((text, font, cap_height(font)))
            if not ok:
                continue
            gap = int(size * .13)
            if sum(i[2] for i in items) + gap * (len(items) - 1) <= box_h:
                return items, gap
        font = get_font(60 * S)
        return [(msg['main'], font, cap_height(font))], 0
    words = msg['main'].split()
    for size in range(150 * S, 34 * S - 1, -2 * S):
        font = get_font(size)
        lines = wrap_words(words, font, box_w)
        if lines is None or len(lines) > 3:
            continue
        cap, gap = cap_height(font), int(size * .26)
        if len(lines) * cap + (len(lines) - 1) * gap <= box_h:
            return [(line, font, cap) for line in lines], gap
    font = get_font(34 * S)
    return [(msg['main'], font, cap_height(font))], 0


def draw_arrow(draw, x, cy, length, width, color):
    r = width / 2
    draw.line([(x, cy), (x + length, cy)], fill=color, width=int(width))
    head = length * .42
    draw.line([(x + length - head, cy - head), (x + length, cy), (x + length - head, cy + head)], fill=color,
              width=int(width), joint='curve')
    for px_, py_ in ((x, cy), (x + length, cy), (x + length - head, cy - head), (x + length - head, cy + head)):
        draw.ellipse((px_ - r, py_ - r, px_ + r, py_ + r), fill=color)


def generate_preview(source, headline, brand_color='#1375d7', brand_name='', logo=None, cta='', mirror=False):
    """trustedDialog-Preview (1088 x 464): Marke, dominante Botschaft, ein CTA, ein Motiv, KI-Kennzeichnung."""
    S = 2  # Supersampling für glatte Kanten und Schrift
    W, H = PREVIEW_SIZE
    WS, HS = W * S, H * S
    brand, fg = panel_colors(safe_brand_rgb(brand_color))
    PT, PB, M, TEXT_W = 522, 458, 52, 366          # Panel oben/unten (x), Rand, Textbreite -> Textfläche ca. 40-45 %
    TOP, BOTTOM = 40, 40

    def X(x):                                         # Spiegelung
        return WS - x * S if mirror else x * S

    canvas = Image.new('RGBA', (WS, HS), (255, 255, 255, 255))
    art_w = (W - 380) * S
    art = smart_fit(source, (art_w, HS))
    canvas.paste(art, (0 if mirror else WS - art_w, 0))
    draw = ImageDraw.Draw(canvas)
    draw.polygon([(X(0), 0), (X(PT), 0), (X(PB), HS), (X(0), HS)], fill=brand)
    ox = (W - M - TEXT_W) * S if mirror else M * S    # linke Kante des Textblocks
    box_w = TEXT_W * S

    # 1) Marke: Logo (CI) oder Markenname
    y_cursor = TOP * S
    logo_h = 60 * S
    brand_bottom = y_cursor
    if logo is not None:
        probe = logo.resize((32, max(1, int(32 * logo.height / logo.width))))
        opaque = [p for p in probe.getdata() if p[3] > 128]
        mean = tuple(sum(p[i] for p in opaque) // len(opaque) for i in range(3)) if opaque else (0, 0, 0)
        chip = contrast(mean, brand) < 3                # Logo würde auf der Markenfarbe untergehen -> weißer Chip
        pad_x, pad_y = (14 * S, 9 * S) if chip else (0, 0)
        scale = min((box_w * .72 - 2 * pad_x) / logo.width, (logo_h - 2 * pad_y) / logo.height, 1.6 * S)
        lw, lh = max(1, int(logo.width * scale)), max(1, int(logo.height * scale))
        mark = logo.resize((lw, lh), Image.Resampling.LANCZOS)
        if chip:
            draw.rounded_rectangle((ox, y_cursor, ox + lw + 2 * pad_x, y_cursor + lh + 2 * pad_y), radius=14 * S,
                                   fill=(255, 255, 255))
        canvas.alpha_composite(mark, (int(ox + pad_x), int(y_cursor + pad_y + (logo_h - 2 * pad_y - lh) / 2)))
        brand_bottom = y_cursor + logo_h
    elif brand_name:
        label = short(brand_name, 22).upper()
        for size in range(58 * S, 26 * S - 1, -2 * S):
            font = get_font(size)
            if font.getlength(label) <= box_w:
                break
        draw.text((ox, y_cursor + logo_h / 2 + cap_height(font) / 2), label, font=font, fill=fg, anchor='ls')
        brand_bottom = y_cursor + logo_h

    # 2) CTA-Button unten
    cta_text = (cta or '').strip().upper() or headline_cta(headline)
    btn_h = 66 * S
    btn_top = HS - BOTTOM * S - btn_h
    for size in range(34 * S, 20 * S - 1, -S):
        cfont = get_font(size)
        arrow_len = int(size * .95)
        tw = cfont.getlength(cta_text)
        btn_w = int(tw + arrow_len + 28 * S * 2 + 14 * S)
        if btn_w <= box_w:
            break
    on_dark = fg == (255, 255, 255)
    btn_fill = (255, 255, 255) if on_dark else (17, 17, 17)
    btn_text = brand if on_dark and contrast(brand, (255, 255, 255)) >= 3 else ((17, 17, 17) if on_dark else (255, 255, 255))
    draw.rounded_rectangle((ox, btn_top, ox + btn_w, btn_top + btn_h), radius=btn_h // 2, fill=btn_fill)
    cy = btn_top + btn_h / 2
    draw.text((ox + 28 * S, cy + cap_height(cfont) / 2), cta_text, font=cfont, fill=btn_text, anchor='ls')
    draw_arrow(draw, ox + 28 * S + tw + 14 * S, cy, arrow_len, max(3, size * .13), btn_text)

    # 3) Hauptbotschaft in der verbleibenden Zone, vertikal zentriert
    msg = campaign_message(headline)
    zone_top = brand_bottom + 22 * S
    zone_bottom = btn_top - 22 * S
    items, gap = fit_message(msg, box_w, zone_bottom - zone_top, S)
    total = sum(i[2] for i in items) + gap * (len(items) - 1)
    y = zone_top + (zone_bottom - zone_top - total) * .45
    for text, font, cap in items:
        y += cap
        draw.text((ox, y), text, font=font, fill=fg, anchor='ls')
        y += gap

    # 4) KI-Kennzeichnung (klein, an der äußeren Motivecke)
    label_font = get_font(19 * S)
    label = 'KI-generiert'
    lw_ = label_font.getlength(label)
    pw, ph = int(lw_ + 24 * S), int(cap_height(label_font) + 14 * S)
    px0 = 18 * S if mirror else WS - 18 * S - pw
    py0 = HS - 16 * S - ph
    overlay = Image.new('RGBA', (WS, HS), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.rounded_rectangle((px0, py0, px0 + pw, py0 + ph), radius=ph // 2, fill=(0, 0, 0, 120))
    od.text((px0 + 12 * S, py0 + ph / 2 + cap_height(label_font) / 2), label, font=label_font, fill=(255, 255, 255, 235),
            anchor='ls')
    canvas.alpha_composite(overlay)
    return canvas.convert('RGB').resize((W, H), Image.Resampling.LANCZOS)


def headline_cta(headline):
    return campaign_message(headline)['cta']


@st.cache_data(show_spinner=False, max_entries=24)
def render_banner(source_bytes, logo_bytes, headline, brand_color, brand_name, cta, mirror):
    source = flatten_to_rgb(image_from_bytes(source_bytes))
    logo = image_from_bytes(logo_bytes) if logo_bytes else None
    return png_data(generate_preview(source, headline, brand_color, brand_name, logo, cta, mirror))


# ====================================================================== UI ===
SEAL = remote_data_uri(SEAL_URL)
GMX_LOGO = remote_data_uri(GMX_LOGO_URL)

for k, v in {'domain': '', 'sender': 'Absender', 'subject': 'Betreff', 'preheader': 'Preview-Text', 'color': AVATAR_DEFAULT,
             'analysis': None, 'generated_preview': None, 'generated_avatar': '', 'selected_image': '',
             'source_image': None, 'banner_logo': None, 'brand_color': '#1375d7', 'banner_headline': '',
             'banner_cta': '', 'banner_mirror': False}.items():
    st.session_state.setdefault(k, v)


def apply_palette_choice():
    choice = st.session_state.get('palette_choice')
    if choice:
        st.session_state.brand_color = choice


st.title('trustedDialog Preview Builder')
st.caption('Domain eingeben, Vorschläge automatisch erstellen und anschließend direkt bearbeiten.')

st.subheader('1. Unternehmen analysieren')
d1, d2 = st.columns([4, 1])
with d1:
    st.text_input('Für welche Domain soll das trustedDialog Preview generiert werden?', key='domain',
                  placeholder='z. B. www.beispiel.de')
with d2:
    st.write('')
    st.write('')
    analyze_clicked = st.button('Vorschläge erstellen', type='primary', use_container_width=True)
if analyze_clicked:
    try:
        with st.spinner('Website wird analysiert und die Preview vorbereitet …'):
            result = analyze_site(st.session_state.domain)
            st.session_state.analysis = result
            st.session_state.sender = result['brand']
            st.session_state.subject = result['subject']
            st.session_state.preheader = result['preheader']
            st.session_state.banner_headline = result['offers'][0] if result['offers'] else result['subject']
            st.session_state.banner_cta = ''
            st.session_state.generated_avatar = ''
            st.session_state.banner_logo = None
            logo_image = None
            for logo_url in result['logos']:
                try:
                    raw, _, content_type = safe_fetch(logo_url, 3000000)
                except Exception:
                    continue
                if not st.session_state.generated_avatar:
                    st.session_state.generated_avatar = 'data:' + (content_type or 'image/png') + ';base64,' + base64.b64encode(raw).decode()
                if logo_image is None:
                    try:
                        prepared = prepare_logo(image_from_bytes(raw))
                        if prepared is not None:
                            logo_image = prepared
                            st.session_state.banner_logo = png_data(prepared)
                    except Exception:
                        pass
                if st.session_state.generated_avatar and logo_image is not None:
                    break
            ranked = rank_brand_colors(result['color_scores'], logo_image)
            result['colors'] = ranked
            st.session_state.brand_color = ranked[0] if ranked else '#1375d7'
            st.session_state.source_image = None
            fallback = None
            for candidate in result['images']:
                try:
                    selected = image_from_url(candidate)
                except Exception:
                    continue
                if fallback is None:
                    fallback = (candidate, selected)
                if usable_motif(selected):
                    st.session_state.selected_image = candidate
                    st.session_state.source_image = to_bytes(selected, 'JPEG')
                    break
            if st.session_state.source_image is None and fallback is not None:
                st.session_state.selected_image = fallback[0]
                st.session_state.source_image = to_bytes(fallback[1], 'JPEG')
        st.success('Vorschläge wurden erstellt. Alle Inhalte können unten überschrieben werden.')
    except Exception as error:
        st.error(f'Die Website konnte nicht analysiert werden: {error}')

analysis = st.session_state.analysis
if analysis:
    with st.expander('Erkannte Website-Informationen', expanded=False):
        st.write(f"**Marke:** {analysis['brand']}")
        if analysis['offers']:
            st.write('**Gefundene Angebots-Hinweise:** ' + ' · '.join(analysis['offers'][:5]))
        if analysis['description']:
            st.write('**Beschreibung:** ' + analysis['description'][:350])
        st.caption('Bitte prüfen Sie die vorgeschlagenen Inhalte und stellen Sie sicher, dass die erforderlichen Bild- und Markenrechte vorliegen.')
    if analysis['images']:
        choices = analysis['images']
        chosen = st.selectbox('Alternatives Website-Motiv', choices,
                              index=choices.index(st.session_state.selected_image) if st.session_state.selected_image in choices else 0,
                              format_func=lambda x: x.split('/')[-1][:70] or x)
        if st.button('Ausgewähltes Motiv übernehmen'):
            try:
                img = image_from_url(chosen)
                st.session_state.selected_image = chosen
                st.session_state.source_image = to_bytes(img, 'JPEG')
                st.rerun()
            except Exception as error:
                st.error(f'Das Bild konnte nicht übernommen werden: {error}')

st.subheader('2. Inhalte bearbeiten')
l, r = st.columns([.86, 1.14], gap='large')
with l:
    st.text_input('Absender / Marke', key='sender', max_chars=37)
    st.text_input('Betreff', key='subject', max_chars=37)
    st.text_input('Preview-Text', key='preheader', max_chars=37)
    st.color_picker('Fallback-Avatarfarbe', key='color')
    af = st.file_uploader('Avatar / Logo überschreiben', type=['svg', 'png', 'jpg', 'jpeg', 'webp'],
                          help='SVG wird direkt nach dem Upload im Browser in PNG konvertiert und anschließend nur noch als PNG verwendet.')
    pf = st.file_uploader('Preview-Bild überschreiben (1088 × 464 px)', type=['png', 'jpg', 'jpeg', 'webp'])
    with st.expander('Grafik-Einstellungen (generiertes Preview-Bild)', expanded=False):
        st.text_input('Headline in der Grafik', key='banner_headline',
                      help='Eine einzige kurze Botschaft, z. B. „50 %“, „Sale“ oder „Neu entdecken“.')
        st.text_input('Button-Text (CTA)', key='banner_cta', placeholder='automatisch (z. B. JETZT SHOPPEN)')
        st.color_picker('Markenfarbe der Grafik', key='brand_color')
        if analysis and analysis.get('colors'):
            st.selectbox('Erkannte Markenfarben', analysis['colors'], index=None, key='palette_choice',
                         placeholder='Farbe aus der Website wählen', on_change=apply_palette_choice)
        st.checkbox('Text rechts, Motiv links (gespiegelt)', key='banner_mirror')
    if st.session_state.source_image:
        st.session_state.generated_preview = render_banner(
            st.session_state.source_image, st.session_state.banner_logo, st.session_state.banner_headline,
            st.session_state.brand_color, st.session_state.sender, st.session_state.banner_cta,
            bool(st.session_state.banner_mirror))
    else:
        st.session_state.generated_preview = None
    if st.session_state.generated_preview:
        st.download_button('Generiertes Preview-Bild herunterladen', st.session_state.generated_preview,
                           file_name=f"trustedDialog_Preview_{re.sub(r'[^A-Za-z0-9._-]+', '_', st.session_state.sender)}_1088x464.png",
                           mime='image/png', use_container_width=True)

sender, subject, pre = display_text(st.session_state.sender), display_text(st.session_state.subject), display_text(st.session_state.preheader)
download_sender = json.dumps(st.session_state.sender or 'Absender', ensure_ascii=False).replace('<', '\\u003c')
avsrc = uri(af) if af else st.session_state.generated_avatar
psrc = uri(pf) if pf else ('data:image/png;base64,' + base64.b64encode(st.session_state.generated_preview).decode() if st.session_state.generated_preview else '')
letters = e(''.join(x[0] for x in st.session_state.sender.split()[:2]).upper() or 'M')
fallback_color = e(st.session_state.color)
is_svg = str(bool(af and af.name.lower().endswith('.svg'))).lower()
av = (f'<img class="avatar" id="uploaded-avatar" data-is-svg="{is_svg}" src="{avsrc}">' if avsrc
      else f'<span class="avatar fallback" style="background:{fallback_color}">{letters}</span>')
pv = f'<img class="preview" src="{psrc}">' if psrc else '<div class="preview placeholder">Bild einfügen</div>'
seal = f'<img class="seal" src="{SEAL}" alt="trustedDialog Siegel">'


def star_points(cx, cy, R, r):
    return ' '.join(f'{cx + (R if i % 2 == 0 else r) * math.cos(-math.pi / 2 + i * math.pi / 5):.2f},'
                    f'{cy + (R if i % 2 == 0 else r) * math.sin(-math.pi / 2 + i * math.pi / 5):.2f}' for i in range(10))


# Maße stammen aus der Vorlage (373 x 755 px Screenshot); Koordinaten im .screen relativ zur Display-Ecke.
PHONE_TEMPLATE = r'''<!doctype html><html><head><meta charset="utf-8">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Roboto:wght@400;500;700&family=Inter:wght@600&display=swap">
<script src="https://cdn.jsdelivr.net/npm/html2canvas@1.4.1/dist/html2canvas.min.js"></script><style>
*{box-sizing:border-box;margin:0;padding:0}
html,body{background:transparent;font-family:Roboto,"Helvetica Neue",Arial,sans-serif;-webkit-font-smoothing:antialiased}
.stage{display:flex;flex-direction:column;align-items:center}
.phonewrap{position:relative;width:354px;height:732px}
.sidebtn{position:absolute;background:linear-gradient(90deg,#4a4947,#9a9996 50%,#2c2b2a);border-radius:2px}
.phone{position:absolute;left:4px;top:0;width:344px;height:732px;border-radius:56px;background:#2a2927}
.l1,.l2,.l3,.bezel{position:absolute}
.l1{inset:1.5px;border-radius:54.5px;background:#727270}
.l2{inset:2.5px;border-radius:53.5px;background:#fff}
.l3{inset:3.5px;border-radius:52.5px;background:#dcdcdc}
.bezel{inset:6.5px;border-radius:50px;background:#1a1918}
.screen{position:absolute;left:14px;top:13px;width:316px;height:706px;overflow:hidden;border-radius:43px;background:#fff;color:#111}
.abs{position:absolute}
.time{left:21px;top:11px;height:18px;font:600 15px/18px Inter,-apple-system,"SF Pro Text",Roboto,Arial,sans-serif;color:#000}
.island{left:117px;top:12px;width:82px;height:23px;border-radius:12px;background:#0b0b0b}
.island i{position:absolute;right:9px;top:6px;width:11px;height:11px;border-radius:50%;background:radial-gradient(circle,#05051a 30%,#1d2a63 62%,#0b0b0b 100%)}
.signal{left:247px;top:22px;height:3px;display:flex;gap:2px}
.signal i{width:2.6px;height:2.6px;border-radius:50%;background:#c3c3c3}
.wifi{left:265px;top:15px;width:13px;height:10px}
.battery{left:284px;top:15px;width:20px;height:10px;border:1px solid #c6c6c6;border-radius:3.5px}
.battery:before{content:"";position:absolute;left:1.5px;top:1.5px;width:12px;height:5px;border-radius:1.5px;background:#000}
.battery:after{content:"";position:absolute;right:-3px;top:2.2px;width:1.6px;height:3.4px;border-radius:0 1px 1px 0;background:#c6c6c6}
.round{width:36px;height:36px;top:49px;border-radius:50%;background:#fff;box-shadow:0 0 12px rgba(0,0,0,.07);display:flex;align-items:center;justify-content:center}
.hicon{width:21px;height:21px;stroke:#111;fill:none;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}
.title{left:51px;top:54px;font:700 13px/16px Roboto,Arial,sans-serif;color:#000;white-space:nowrap}
.mail{left:51px;top:70px;font:400 10px/12px Roboto,Arial,sans-serif;color:#a6a6a6;white-space:nowrap}
.search{left:6px;top:94px;width:299px;height:35px;border-radius:18px;background:#fdfdfb;box-shadow:0 0 12px rgba(0,0,0,.07);display:flex;align-items:center;padding-left:11px;gap:9px;color:#6f6f6f;font-size:15px}
.search svg{width:18px;height:18px;stroke:#111;fill:none;stroke-width:2.2;stroke-linecap:round}
.hline{left:6px;width:299px;height:1px}
.dots{left:6px;top:155px;height:4px;display:flex;gap:4px}
.dots i{width:4px;height:4px;border-radius:50%;background:#3d8ad4}
.dots i:nth-child(1){opacity:.45}.dots i:nth-child(2){opacity:.75}
.recv{left:43px;top:150px;font:400 11px/14px Roboto,Arial,sans-serif;color:#4a4a4a;white-space:nowrap}
.list{left:0;top:174px;width:316px}
.row{position:relative;height:92.5px}
.row:after{content:"";position:absolute;left:23px;right:0;bottom:0;height:1px;background:#d9d9d9}
.row.last:after{display:none}
.row.td{height:193px}
.avatar{position:absolute;left:19px;top:10px;width:36px;height:36px;border-radius:50%;object-fit:cover;display:flex;align-items:center;justify-content:center;color:#fff;font:700 13px/36px Roboto,Arial,sans-serif;text-align:center;background:#8ea8ce}
.td .avatar{top:11px}
.senderline{position:absolute;left:65px;top:11px;height:20px;display:flex;align-items:center;white-space:nowrap}
.sender{font:700 14px/20px Roboto,Arial,sans-serif;color:#000;max-width:170px;overflow:hidden;white-space:nowrap}
.seal{width:14px;height:14px;flex:0 0 14px;margin-left:5px;object-fit:contain}
.subject,.pre{position:absolute;left:65px;width:239px;height:20px;font:400 14px/20px Roboto,Arial,sans-serif;white-space:nowrap;overflow:hidden}
.subject{top:32px;color:#111}
.pre{top:55px;color:#a3a3a3}
.rtime{position:absolute;right:12px;top:14px;font:400 11px/14px Roboto,Arial,sans-serif;color:#9e9e9e}
.pwrap{position:absolute;left:65px;top:81px;width:227px;height:96.8px;border-radius:6px;overflow:hidden}
.preview{width:100%;height:100%;object-fit:cover;display:block}
.placeholder{background:#ff00e8;color:#fff;display:flex;align-items:center;justify-content:center;font-size:11px}
.fade{left:0;top:598px;width:316px;height:42px;background:linear-gradient(to bottom,rgba(255,255,255,0),rgba(255,255,255,.95))}
.nav{left:10px;top:638px;width:292px;height:50px;border-radius:25px;background:#fffffe;box-shadow:0 2px 14px rgba(0,0,0,.10)}
.navhl{left:13px;top:641px;width:62px;height:43px;border-radius:22px;background:#ededec}
.navitem{position:absolute;top:641px;width:56px;height:43px;display:flex;flex-direction:column;align-items:center;padding-top:6px;gap:1.5px;font:700 9.6px/11px Roboto,Arial,sans-serif;color:#222;letter-spacing:-.1px}
.navitem svg{width:21px;height:21px;display:block}
.navitem.active{color:#2f6fc0}
.badge{left:52px;top:642px;width:17px;height:17px;border-radius:50%;background:#cc2a22;color:#fff;font:700 10px/17px Roboto,Arial,sans-serif;text-align:center}
.home{left:107px;top:694px;width:103px;height:4px;border-radius:2px;background:#111}
.downloadbar{margin-top:12px;text-align:center}
.downloadbtn{border:1px solid #777;background:#fff;color:#111;border-radius:6px;padding:9px 14px;font:600 13px Arial,sans-serif;cursor:pointer}
.downloadbtn:hover{background:#f4f4f4}
</style></head><body><div class="stage"><div class="phonewrap">
<div class="sidebtn" style="left:0;top:130px;width:4px;height:22px"></div>
<div class="sidebtn" style="left:0;top:178px;width:4px;height:46px"></div>
<div class="sidebtn" style="left:0;top:242px;width:4px;height:46px"></div>
<div class="sidebtn" style="left:348px;top:215px;width:5px;height:73px"></div>
<div class="phone"><div class="l1"></div><div class="l2"></div><div class="l3"></div><div class="bezel"></div>
<div class="screen">
<span class="abs time" id="now">10:03</span>
<span class="abs island"><i></i></span>
<span class="abs signal"><i></i><i></i><i></i><i></i></span>
<svg class="abs wifi" viewBox="0 0 17 12" aria-label="WLAN"><g fill="none" stroke="#000" stroke-width="2" stroke-linecap="round"><path d="M2.7 5.2A8.2 8.2 0 0 1 14.3 5.2"/><path d="M4.9 7.5A5.1 5.1 0 0 1 12.1 7.5"/></g><path d="M8.5 11.2 6.3 9A3.1 3.1 0 0 1 10.7 9Z" fill="#000" stroke="#000" stroke-width="1" stroke-linejoin="round"/></svg>
<span class="abs battery"></span>
<span class="abs round" style="left:6px"><svg class="hicon" viewBox="0 0 24 24"><path d="M14.5 5.5 8 12l6.5 6.5"/></svg></span>
<span class="abs title">Posteingang</span><span class="abs mail">trusteddialog01@gmx.net</span>
<span class="abs round" style="left:225px"><svg class="hicon" viewBox="0 0 24 24"><circle cx="12" cy="12" r="8.5"/><path d="m8.4 12.2 2.5 2.5 4.8-5.2"/></svg></span>
<span class="abs round" style="left:270px"><svg class="hicon" viewBox="0 0 24 24"><path d="M11 4H6.5A2.5 2.5 0 0 0 4 6.5v11A2.5 2.5 0 0 0 6.5 20h11a2.5 2.5 0 0 0 2.5-2.5V13"/><path d="M18.4 2.8a1.9 1.9 0 0 1 2.7 2.7L12 14.6l-3.8 1 1-3.8z"/></svg></span>
<div class="abs search"><svg viewBox="0 0 24 24"><circle cx="10.5" cy="10.5" r="6.5"/><path d="m15.4 15.4 5 5"/></svg>Suchen</div>
<span class="abs hline" style="top:141px;background:#e6e6e6"></span>
<span class="abs dots"><i></i><i></i><i></i></span><span class="abs recv">E-Mails empfangen</span>
<span class="abs hline" style="top:173px;background:#ececec"></span>
<div class="abs list">
<div class="row td"><div>__AV__</div><div class="senderline"><span class="sender">__SENDER__</span>__SEAL__</div><div class="subject">__SUBJECT__</div><div class="pre">__PRE__</div><div class="rtime" data-off="-3"></div><div class="pwrap">__PV__</div></div>
<div class="row"><span class="avatar">OH</span><div class="senderline"><span class="sender">Otto Holler</span></div><div class="subject">Gewünschte Bilder</div><div class="pre">Hallo zusammen, anbei findet Ihr die…</div><div class="rtime" data-off="-15"></div></div>
<div class="row"><img class="avatar" src="__GMXLOGO__" alt="GMX"><div class="senderline"><span class="sender">GMX Magazin</span>__SEAL__</div><div class="subject">Traumhaus auf Föhr zu gewinnen: 8…</div><div class="pre">Jetzt Lose bei GMX Lotto sichern! W…</div><div class="rtime" data-off="-34"></div></div>
<div class="row"><span class="avatar">SW</span><div class="senderline"><span class="sender">Shopping World</span></div><div class="subject">Neue Deals am Wochenende</div><div class="pre">Jetzt entdecken</div><div class="rtime" data-off="-47"></div></div>
<div class="row last"><span class="avatar">FF</span><div class="senderline"><span class="sender">Fred Fritt</span></div><div class="subject">Klassentreffen</div><div class="pre">Hallo zusammen, vielen Dank für das to…</div><div class="rtime" data-off="-59"></div></div>
</div>
<div class="abs fade"></div>
<div class="abs nav"></div><div class="abs navhl"></div>
<div class="navitem active" style="left:16px"><svg viewBox="0 0 24 24"><rect x="1.5" y="4.5" width="21" height="15" fill="#3a78c8"/><path d="M1.5 5.5 12 13l10.5-7.5M1.5 19l7.8-7M22.5 19l-7.8-7" fill="none" stroke="#fff" stroke-width="1.5"/></svg>E-Mail</div>
<div class="navitem" style="left:72px"><svg viewBox="0 0 24 24"><path d="M3 6.5A1.5 1.5 0 0 1 4.5 5H9l2 2.5h8.5A1.5 1.5 0 0 1 21 9v9a1.5 1.5 0 0 1-1.5 1.5h-15A1.5 1.5 0 0 1 3 18z" fill="#111"/></svg>Dateien</div>
<div class="navitem" style="left:127px"><svg viewBox="0 0 24 24"><path d="M3 8.5v10A2.5 2.5 0 0 0 5.5 21H15" fill="none" stroke="#111" stroke-width="1.8" stroke-linecap="round"/><rect x="6.5" y="3" width="15" height="14" rx="2" fill="#111"/><path d="m8.5 14.5 3-3.6 2.2 2.5 2-2.2 3 3.3z" fill="#fff"/><circle cx="17.5" cy="7" r="1.4" fill="#fff"/></svg>Fotos</div>
<div class="navitem" style="left:183px"><svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="10.5" fill="#111"/><polygon points="__STAR_L__" fill="#fff"/><polygon points="__STAR_R__" fill="#fff"/><path d="M6.2 13.6h11.6a5.8 5.8 0 0 1-11.6 0z" fill="#fff"/></svg>Vorteile</div>
<div class="navitem" style="left:239px"><svg viewBox="0 0 24 24"><rect x="2.5" y="3.5" width="19" height="17" rx="1.5" fill="#111"/><rect x="7" y="6.5" width="12" height="3" fill="none" stroke="#fff" stroke-width="1"/><path d="M7 12.5h4.5M7 15.5h4.5" stroke="#fff" stroke-width="1.2"/><rect x="13.5" y="11.5" width="5.5" height="5" fill="none" stroke="#fff" stroke-width="1"/><path d="M4.8 7v10" stroke="#fff" stroke-width="1"/></svg>News</div>
<span class="abs badge">4</span>
<div class="abs home"></div>
</div></div></div>
<div class="downloadbar"><button class="downloadbtn" onclick="downloadPreview()">GMX-Vorschau als PNG herunterladen</button></div>
</div>
<script>
const p=n=>String(n).padStart(2,'0'),fmt=d=>p(d.getHours())+':'+p(d.getMinutes());
function tick(){let n=new Date();document.getElementById('now').textContent=fmt(n);document.querySelectorAll('[data-off]').forEach(x=>x.textContent=fmt(new Date(n.getTime()+Number(x.dataset.off)*60000)))}
tick();setInterval(tick,30000);
async function svgAvatarToPngImmediately(){
 const img=document.getElementById('uploaded-avatar');
 if(!img || img.dataset.isSvg!=='true') return;
 await new Promise(resolve=>{if(img.complete) resolve(); else {img.onload=resolve;img.onerror=resolve;}});
 const source=new Image();
 await new Promise((resolve,reject)=>{source.onload=resolve;source.onerror=reject;source.src=img.currentSrc||img.src;});
 const size=256;
 const canvas=document.createElement('canvas');canvas.width=size;canvas.height=size;
 const ctx=canvas.getContext('2d');ctx.clearRect(0,0,size,size);
 const sw=source.naturalWidth||size,sh=source.naturalHeight||size;
 const scale=Math.max(size/sw,size/sh),dw=sw*scale,dh=sh*scale;
 ctx.drawImage(source,(size-dw)/2,(size-dh)/2,dw,dh);
 img.src=canvas.toDataURL('image/png');
 img.removeAttribute('data-is-svg');
}
svgAvatarToPngImmediately().catch(err=>console.warn('SVG-to-PNG conversion failed',err));
async function downloadPreview(){
 const button=document.querySelector('.downloadbtn');
 const phone=document.querySelector('.phonewrap');
 const original=button.textContent;
 try{
  button.disabled=true;button.textContent='PNG wird erstellt…';
  if(typeof html2canvas==='undefined') throw new Error('html2canvas konnte nicht geladen werden');
  await document.fonts.ready;
  await Promise.all(Array.from(phone.querySelectorAll('img')).map(img=>img.complete ? Promise.resolve() : new Promise(resolve=>{img.onload=resolve;img.onerror=resolve;})));
  const canvas=await html2canvas(phone,{
   backgroundColor:null,
   scale:2,
   useCORS:true,
   allowTaint:false,
   logging:false,
   width:354,
   height:732,
   scrollX:0,
   scrollY:0,
   onclone:(doc)=>{
    doc.querySelectorAll('img.preview').forEach(img=>{
     const wrap=img.closest('.pwrap');
     if(wrap){
      wrap.style.backgroundImage='url("'+img.src+'")';
      wrap.style.backgroundSize='cover';
      wrap.style.backgroundPosition='center center';
      wrap.style.backgroundRepeat='no-repeat';
      img.style.visibility='hidden';
     }
    });
    doc.querySelectorAll('img.avatar').forEach(img=>{
     img.style.width='36px';img.style.height='36px';
     img.style.minWidth='36px';img.style.minHeight='36px';
     img.style.maxWidth='36px';img.style.maxHeight='36px';
     img.style.borderRadius='50%';img.style.objectFit='cover';
     img.style.objectPosition='center center';img.style.display='block';img.style.visibility='visible';
    });
   }
  });
  const rawSender=__DLSENDER__;
  const safeSender=String(rawSender).trim().replace(/[\\/:*?"<>|]+/g,'_')||'Absender';
  const blob=await new Promise(resolve=>canvas.toBlob(resolve,'image/png'));
  if(!blob) throw new Error('PNG-Blob konnte nicht erzeugt werden');
  const url=URL.createObjectURL(blob);
  const link=document.createElement('a');
  link.download='GMX_trustedDialogPreview_'+safeSender+'.png';
  link.href=url;
  document.body.appendChild(link);link.click();link.remove();
  setTimeout(()=>URL.revokeObjectURL(url),1000);
 }catch(err){
  console.error(err);
  alert('Die PNG-Datei konnte nicht erzeugt werden: '+err.message);
 }finally{button.disabled=false;button.textContent=original;}
}
</script></body></html>'''

H = PHONE_TEMPLATE
for token, value in {'__AV__': av, '__PV__': pv, '__SEAL__': seal, '__SENDER__': sender, '__SUBJECT__': subject,
                     '__PRE__': pre, '__GMXLOGO__': GMX_LOGO, '__DLSENDER__': download_sender,
                     '__STAR_L__': star_points(8, 9.4, 2.9, 1.2), '__STAR_R__': star_points(16, 9.4, 2.9, 1.2)}.items():
    H = H.replace(token, value)
with r:
    st.subheader('3. GMX Live-Vorschau')
    st.caption('Smartphone · GMX.DE · iOS')
    components.html(H, height=810, scrolling=False)
st.caption('Echtes trustedDialog SVG-Siegel · SVG-Avatar-Upload · Live-Zeit mit früheren Mailzeiten · Maße nach GMX-App-Vorlage')
