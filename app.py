import base64, colorsys, html, io, ipaddress, json, os, re, socket
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
AVATAR_DEFAULT = '#B8DDFD'     # Fallback-Avatar (Initialen) laut GMX-Vorlage
AVATAR_BG_DEFAULT = '#FFFFFF'  # Hintergrund hinter Logo-Avataren der tD-Mail (transparente SVG/PNG)


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
    """Nur escapen; das Kürzen mit „…“ übernimmt der Browser pixelgenau (Siegel und Uhrzeit bleiben sichtbar)."""
    return e(re.sub(r'\s+', ' ', x or '').strip()[:80])


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
# Markenname des Absenders
# ---------------------------------------------------------------------------
LEGAL_SUFFIX_RE = re.compile(
    r'(?:,?\s+)(?:GmbH\s*&\s*Co\.?\s*(?:KGaA|KG|OHG)|GmbH|gGmbH|AG|SE|KGaA|KG|OHG|UG(?:\s*\(haftungsbeschränkt\))?|'
    r'e\.\s?K\.?|e\.\s?V\.?|Inc\.?|Ltd\.?|LLC|S\.A\.?|B\.V\.?|N\.V\.?|S\.r\.l\.?|Corp\.?|Co\.)\s*$', re.I)
SHOP_SUFFIX_RE = re.compile(
    r'(?:\s*[-–|:]\s*|\s+)(?:offizielle[rs]?\s+)?(?:online[- ]?shop|onlineshop|shop online|webshop|online[- ]?store|'
    r'official (?:online )?(?:store|site|website)|offizielle (?:website|seite|homepage))\s*$', re.I)
GENERIC_NAMES = {'home', 'startseite', 'homepage', 'start', 'shop', 'onlineshop', 'online shop', 'willkommen', 'welcome',
                 'index', 'website', 'offizielle website', 'official website', 'mode', 'news', 'login', 'anmelden'}
TITLE_SPLIT_RE = re.compile(r'\s+[|–—·•»:]\s+|\s+-\s+|\s*\|\s*')
SECOND_LEVEL = {'co', 'com', 'org', 'net', 'ac', 'gv', 'or', 'ne', 'gov', 'edu'}


def brand_key(value):
    value = (value or '').lower()
    for a, b in (('ä', 'ae'), ('ö', 'oe'), ('ü', 'ue'), ('ß', 'ss'), ('&', 'und')):
        value = value.replace(a, b)
    return re.sub(r'[^a-z0-9]', '', value)


def domain_label(host):
    parts = [p for p in (host or '').lower().split('.') if p and p != 'www']
    if len(parts) >= 3 and parts[-2] in SECOND_LEVEL:
        return parts[-3]
    return parts[-2] if len(parts) >= 2 else (parts[0] if parts else '')


def clean_brand(value):
    value = re.sub(r'\s+', ' ', html.unescape(value or '')).strip(' -|–—·•:»«"\'®™©')
    value = re.sub(r'^(?:©|\(c\)|copyright)\s*(?:\d{4}(?:\s*[-–]\s*\d{4})?)?\s*', '', value, flags=re.I)
    for _ in range(2):
        value = SHOP_SUFFIX_RE.sub('', value).strip(' -|–—·,')
        value = LEGAL_SUFFIX_RE.sub('', value).strip(' -|–—·,')
    if ' ' not in value:                                   # „dm.de“ / „home24.de“ -> Markenname ohne Endung
        value = re.sub(r'(?i)^(?:www\.)?([\w-]+)\.(?:de|com|at|ch|net|org|eu|shop|info|biz|io|co\.uk|nl|fr|it)$', r'\1', value)
    return value.strip(' ®™')


def json_ld_names(soup):
    """Liefert (Name, Gewicht) aus JSON-LD: Organization/Brand/Store > WebSite > publisher."""
    out = []

    def walk(node, depth=0):
        if depth > 6:
            return
        if isinstance(node, list):
            for item in node:
                walk(item, depth + 1)
            return
        if not isinstance(node, dict):
            return
        kind = node.get('@type', '')
        kind = ' '.join(kind) if isinstance(kind, list) else str(kind)
        name = node.get('name') if isinstance(node.get('name'), str) else ''
        if name:
            if re.search(r'Organization|Corporation|Brand|Store|LocalBusiness|NewsMediaOrganization', kind):
                out.append((name, 6))
            elif 'WebSite' in kind:
                out.append((name, 4))
        for key in ('publisher', 'brand', 'author', '@graph', 'mainEntity'):
            if key in node:
                walk(node[key], depth + 1)

    for tag in soup.find_all('script', attrs={'type': 'application/ld+json'})[:12]:
        try:
            walk(json.loads(tag.string or tag.get_text() or ''))
        except Exception:
            continue
    return out


def detect_brand(soup, host):
    """Markenname des Absenders. Quellen werden gewichtet und gegen die Domain geprüft,
    damit nicht ein Seitentitel wie „Mode online kaufen“ als Absender landet."""
    label = domain_label(host)
    label_key = brand_key(label)
    candidates = []

    def add(value, weight):
        value = clean_brand(value)
        if 2 <= len(value) <= 40 and value.lower() not in GENERIC_NAMES:
            candidates.append((value, weight))

    add(meta(soup, 'og:site_name'), 6)
    add(meta(soup, 'application-name'), 5)
    add(meta(soup, 'apple-mobile-web-app-title'), 5)
    for name, weight in json_ld_names(soup):
        add(name, weight)
    title = soup.title.get_text(' ', strip=True) if soup.title else ''
    for source, weight in ((title, 3), (meta(soup, 'og:title'), 2)):
        parts = [p for p in TITLE_SPLIT_RE.split(source or '') if p.strip()]
        for index, part in enumerate(parts):
            add(part, weight + (1 if index in (0, len(parts) - 1) and len(parts) > 1 else 0))
    for tag in soup.find_all('img')[:80]:
        marker = (' '.join(tag.get('class', [])) + ' ' + (tag.get('id') or '') + ' ' + (tag.get('src') or '')).lower()
        if 'logo' in marker:
            add(re.sub(r'(?i)\s*(?:-\s*)?logo\b.*$', '', tag.get('alt') or tag.get('title') or ''), 3)
    twitter = meta(soup, 'twitter:site').lstrip('@')
    if twitter:
        add(twitter, 1)
    copyright_match = re.search(r'(?:©|&copy;|Copyright)\s*(?:\d{4}(?:\s*[-–]\s*\d{4})?)?\s*([A-ZÄÖÜ][\w&.\- ]{1,40}?)'
                                r'(?:\s*(?:GmbH|AG|SE|KG|Inc|Ltd)\b|[.,|]|\s{2}|$)', soup.get_text(' ', strip=True)[-6000:])
    if copyright_match:
        add(copyright_match.group(1), 2)

    best, best_score = '', -99.0
    for value, weight in candidates:
        key = brand_key(value)
        if not key:
            continue
        score = weight
        if label_key and key == label_key:
            score += 10
        elif label_key and len(label_key) >= 2 and (key.startswith(label_key) or label_key.startswith(key)):
            score += 7
        elif label_key and len(label_key) >= 3 and (label_key in key or key in label_key):
            score += 5
        elif not label_key or weight < 5:
            score -= 4                      # Titel-Fragment ohne Bezug zur Domain -> eher Slogan als Marke
        words = len(value.split())
        score -= max(0, words - 3) * 1.5 + len(value) * .04
        if value.isupper() and len(value) > 4 and words == 1 and label_key and key == label_key:
            score += .5                     # Schreibweise der Marke (z. B. „OTTO“) beibehalten
        if score > best_score:
            best, best_score = value, score
    if best and best_score >= 3:
        return best
    return label.replace('-', ' ').title() if label else host


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
    host = (urlparse(final_url).hostname or '').replace('www.', '')
    brand = detect_brand(soup, host)
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
    avatar_sources = collect_avatar_sources(soup, final_url)
    offer = offers[0] if offers else ''
    if offer:
        subject = short(('Jetzt ' + offer + ' sichern') if len(offer) < 26 else offer)
        preheader = short('Angebot jetzt entdecken')
    else:
        subject = short('Neuigkeiten von ' + brand)
        preheader = short('Jetzt Vorteile entdecken')
    return {'url': final_url, 'brand': short(brand), 'description': description, 'offers': offers,
            'color_scores': color_scores, 'colors': rank_brand_colors(color_scores), 'images': images,
            'logos': logos, 'avatar_sources': avatar_sources, 'subject': subject, 'preheader': preheader}


# ---------------------------------------------------------------------------
# Avatar-Kandidaten (Icons und Logos der Website)
# ---------------------------------------------------------------------------
def icon_size_hint(value):
    sizes = [int(a) * int(b) for a, b in re.findall(r'(\d+)\s*x\s*(\d+)', value or '', re.I)]
    return int(max(sizes) ** .5) if sizes else 0


SVG_CASE = ['viewBox', 'preserveAspectRatio', 'gradientUnits', 'gradientTransform', 'patternUnits', 'patternTransform',
            'clipPathUnits', 'maskUnits', 'maskContentUnits', 'stdDeviation', 'textLength', 'lengthAdjust', 'baseProfile',
            'clipPath', 'linearGradient', 'radialGradient', 'feGaussianBlur', 'feOffset', 'feFlood', 'feComposite',
            'feMerge', 'feMergeNode', 'feColorMatrix', 'feBlend', 'textPath', 'foreignObject', 'xlink:href']


def fix_svg_case(markup):
    """Der HTML-Parser schreibt Inline-SVG klein (viewbox, lineargradient) – SVG braucht die Originalschreibweise."""
    for name in SVG_CASE:
        markup = re.sub(r'(?<=[\s<"/])' + name.lower() + r'(?=[\s=>/])', name, markup)
    if 'xmlns=' not in markup[:300]:
        markup = markup.replace('<svg', '<svg xmlns="http://www.w3.org/2000/svg"', 1)
    return markup


def collect_avatar_sources(soup, base_url):
    """Sammelt Avatar-Kandidaten mit Priorität. Rückgabe: Liste von (Priorität, Quelle, Bezeichnung);
    Quelle ist eine URL oder ein Inline-SVG (beginnt mit '<svg')."""
    found = []
    manifest = ''
    for link in soup.find_all('link', href=True):
        rel = ' '.join(link.get('rel', [])).lower()
        href = urljoin(base_url, link['href'])
        size = icon_size_hint(link.get('sizes'))
        if 'apple-touch-icon' in rel:
            found.append((10 + min(size, 512) / 256, href, f'App-Icon{f" {size}px" if size else ""}'))
        elif 'mask-icon' in rel:
            found.append((2, href, 'Masken-Icon (SVG)'))
        elif 'icon' in rel:
            svg = 'svg' in (link.get('type') or '') or href.lower().split('?')[0].endswith('.svg')
            found.append((7 + (2 if svg else 0) + min(size, 256) / 128, href, 'Favicon (SVG)' if svg else
                          f'Favicon{f" {size}px" if size else ""}'))
        elif 'manifest' in rel and not manifest:
            manifest = href
    tile = meta(soup, 'msapplication-TileImage')
    if tile:
        found.append((6, urljoin(base_url, tile), 'Kachel-Icon'))
    for tag in soup.find_all('script', attrs={'type': 'application/ld+json'})[:12]:
        for logo in re.findall(r'"logo"\s*:\s*(?:\{[^}]*?"url"\s*:\s*)?"([^"]+)"', tag.string or tag.get_text() or ''):
            found.append((8.5, urljoin(base_url, logo), 'Logo (strukturierte Daten)'))
    for tag in soup.find_all('img'):
        src = tag.get('src') or tag.get('data-src') or tag.get('data-lazy-src')
        marker = (' '.join(tag.get('class', [])) + ' ' + (tag.get('id') or '') + ' ' + (tag.get('alt') or '') + ' '
                  + (src or '')).lower()
        if src and 'logo' in marker and not src.startswith('data:image/gif'):
            found.append((5, urljoin(base_url, src), 'Logo-Grafik der Seite'))
    for svg in soup.find_all('svg')[:60]:
        parents = [p for p in svg.parents if getattr(p, 'name', None) in ('a', 'div', 'span', 'header')][:3]
        marker = (' '.join(svg.get('class', [])) + ' ' + (svg.get('id') or '') + ' ' + (svg.get('aria-label') or '') +
                  ' ' + ' '.join(' '.join(p.get('class', [])) + ' ' + (p.get('id') or '') for p in parents)).lower()
        if 'logo' in marker and len(str(svg)) < 150000 and not svg.find('use'):
            found.append((4, fix_svg_case(str(svg)), 'Logo (Inline-SVG)'))
    if manifest:
        try:
            raw, final, _ = safe_fetch(manifest, 300000)
            for icon in json.loads(raw.decode('utf-8', errors='ignore')).get('icons', [])[:8]:
                if icon.get('src'):
                    size = icon_size_hint(icon.get('sizes'))
                    found.append((9 + min(size, 512) / 256, urljoin(final, icon['src']),
                                  f'Web-App-Icon{f" {size}px" if size else ""}'))
        except Exception:
            pass
    found.append((1, urljoin(base_url, '/favicon.ico'), 'Favicon (Standard)'))
    found.sort(key=lambda item: item[0], reverse=True)
    out, seen = [], set()
    for priority, source, label in found:
        if source not in seen:
            seen.add(source)
            out.append((priority, source, label))
    return out[:16]


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


def is_svg_bytes(raw):
    head = raw[:2048].lstrip().lower()
    return head.startswith(b'<svg') or (head.startswith(b'<?xml') and b'<svg' in raw[:4096].lower()) or \
        (head.startswith(b'<!--') and b'<svg' in raw[:4096].lower())


def sized_svg(raw):
    """SVG ohne width/height erhält Maße aus der viewBox – sonst zeichnet der Browser es nicht zuverlässig in ein Canvas."""
    text = raw.decode('utf-8', errors='ignore')
    match = re.search(r'<svg\b[^>]*>', text, re.I)
    if not match:
        return raw
    tag = match.group(0)
    if 'xmlns=' not in tag:
        tag = tag[:-1].rstrip('/') + ' xmlns="http://www.w3.org/2000/svg">' if not tag.endswith('/>') else tag
    width = re.search(r'\swidth\s*=\s*["\']\s*([\d.]+)(px)?\s*["\']', tag)
    height = re.search(r'\sheight\s*=\s*["\']\s*([\d.]+)(px)?\s*["\']', tag)
    view = re.search(r'viewBox\s*=\s*["\']\s*[-\d.]+[\s,]+[-\d.]+[\s,]+([\d.]+)[\s,]+([\d.]+)', tag, re.I)
    if not (width and height):
        w, h = (float(view.group(1)), float(view.group(2))) if view else (256.0, 256.0)
        tag = re.sub(r'\s(width|height)\s*=\s*["\'][^"\']*["\']', '', tag)
        tag = tag.replace('<svg', f'<svg width="{w:g}" height="{h:g}"', 1)
    return (text[:match.start()] + tag + text[match.end():]).encode('utf-8')


def avatar_data_uri(raw):
    """Bilddaten -> Data-URI für den Avatar. SVG bleibt Vektor (mit Maßen), alles andere wird PNG (max. 256 px).
    Rückgabe (data_uri, Breite, Höhe) oder None, wenn es kein brauchbares Bild ist."""
    if not raw:
        return None
    if is_svg_bytes(raw):
        data = sized_svg(raw)
        if b'<script' in data.lower():
            return None
        return 'data:image/svg+xml;base64,' + base64.b64encode(data).decode(), 0, 0
    try:
        image = Image.open(io.BytesIO(raw))
        if getattr(image, 'format', '') == 'ICO':
            sizes = sorted(image.info.get('sizes', []) or [image.size])
            image.size = sizes[-1]
        image.load()
    except Exception:
        return None
    image = image.convert('RGBA')
    if min(image.size) < 16:
        return None
    width, height = image.size
    image.thumbnail((256, 256), Image.Resampling.LANCZOS)
    return 'data:image/png;base64,' + base64.b64encode(png_data(image)).decode(), width, height


def load_avatar_options(sources, limit=8):
    """Lädt die Avatar-Kandidaten, verwirft Duplikate und unbrauchbare Dateien."""
    options, hashes = [], set()
    for priority, source, label in sources:
        if len(options) >= limit:
            break
        try:
            raw = source.encode('utf-8') if source.lstrip().startswith('<svg') else safe_fetch(source, 2500000)[0]
        except Exception:
            continue
        result = avatar_data_uri(raw)
        if not result:
            continue
        data, width, height = result
        digest = hash(data)
        if digest in hashes:
            continue
        hashes.add(digest)
        score = priority + (2 if min(width, height) >= 120 else -3 if 0 < min(width, height) < 48 else 0)
        if width and height and not .6 <= width / height <= 1.6:
            score -= 2                                    # breite Logos passen schlechter in den runden Avatar
        detail = f'{width}×{height}px' if width else 'SVG'
        options.append({'src': data, 'label': label, 'detail': detail, 'score': score,
                        'url': '' if source.lstrip().startswith('<svg') else source})
    options.sort(key=lambda item: item['score'], reverse=True)
    return options


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

for k, v in {'domain': '', 'sender': 'Marke', 'subject': 'Betreff', 'preheader': 'Preview-Text', 'color': AVATAR_DEFAULT,
             'analysis': None, 'generated_preview': None, 'avatar_options': [], 'avatar_choice': -1,
             'avatar_bg': AVATAR_BG_DEFAULT, 'avatar_fit': 'Eingepasst', 'avatar_pad': 0, 'selected_image': '',
             'source_image': None, 'banner_logo': None, 'brand_color': '#1375d7', 'banner_headline': '',
             'banner_cta': '', 'banner_mirror': False}.items():
    st.session_state.setdefault(k, v)


def apply_palette_choice():
    choice = st.session_state.get('palette_choice')
    if choice:
        st.session_state.brand_color = choice


STICKY_CSS = (
    '<style>'
    '[data-testid="stColumn"]:has(#td-sticky-anchor),[data-testid="column"]:has(#td-sticky-anchor)'
    '{position:sticky;top:4rem;align-self:flex-start;z-index:5}'
    '[data-testid="stColumn"]:has(#td-sticky-anchor) iframe,[data-testid="column"]:has(#td-sticky-anchor) iframe'
    '{height:calc(100vh - 5rem)!important;min-height:520px}'
    '[data-testid="stElementContainer"]:has(#td-sticky-anchor),.element-container:has(#td-sticky-anchor){display:none}'
    '[data-testid="stMainBlockContainer"],.block-container{padding-top:4.25rem!important}'
    '</style><div id="td-sticky-anchor"></div>')


left, right = st.columns([1, 2], gap='large')   # links bearbeiten, rechts die sticky Vorschau
with left:
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
                st.session_state.avatar_options = load_avatar_options(result['avatar_sources'])
                st.session_state.avatar_choice = 0 if st.session_state.avatar_options else -1
                st.session_state.banner_logo = None
                logo_image = None
                for logo_url in result['logos']:
                    try:
                        raw, _, _ = safe_fetch(logo_url, 3000000)
                        prepared = prepare_logo(image_from_bytes(raw))
                    except Exception:
                        continue
                    if prepared is not None:
                        logo_image = prepared
                        st.session_state.banner_logo = png_data(prepared)
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


    def avatar_gallery(options, background):
        """Kleine Vorschau aller gefundenen Avatar-Grafiken (rund, auf dem gewählten Hintergrund)."""
        cells = []
        for index, option in enumerate(options):
            cells.append(
                f'<div style="display:flex;flex-direction:column;align-items:center;gap:4px;width:64px">'
                f'<div style="width:48px;height:48px;border-radius:50%;overflow:hidden;background:{e(background)};'
                f'box-shadow:0 0 0 1px rgba(0,0,0,.12);display:flex;align-items:center;justify-content:center">'
                f'<img src="{option["src"]}" style="width:100%;height:100%;object-fit:contain"></div>'
                f'<span style="font-size:12px;color:#666">{index + 1}</span></div>')
        return '<div style="display:flex;flex-wrap:wrap;gap:6px 4px;margin:2px 0 6px">' + ''.join(cells) + '</div>'


    st.subheader('2. Inhalte bearbeiten')
    st.text_input('Absender / Marke', key='sender', max_chars=37,
                  help='Markenname des Absenders. Zu lange Namen werden in der Vorschau mit „…“ gekürzt, damit das Siegel sichtbar bleibt.')
    st.text_input('Betreff', key='subject', max_chars=37)
    st.text_input('Preview-Text', key='preheader', max_chars=37)
    with st.expander('Avatar der trustedDialog-Mail', expanded=True):
        options = st.session_state.avatar_options
        if options:
            st.markdown(avatar_gallery(options, st.session_state.avatar_bg), unsafe_allow_html=True)
            st.radio('Avatar-Grafik von der Website', list(range(len(options))) + [-1], key='avatar_choice',
                     format_func=lambda i: 'Keine Grafik – Initialen auf Fallback-Farbe' if i == -1 else
                     f'{i + 1} · {options[i]["label"]} ({options[i]["detail"]})')
        else:
            st.caption('Nach der Website-Analyse stehen hier die gefundenen Logos und Icons zur Auswahl.')
        af = st.file_uploader('Eigenes Avatar / Logo hochladen (überschreibt die Auswahl)',
                              type=['svg', 'png', 'jpg', 'jpeg', 'webp'],
                              help='SVG wird im Browser auf dem Avatar-Hintergrund in PNG umgewandelt; transparente Bereiche bleiben weiß.')
        c1, c2 = st.columns(2)
        with c1:
            st.color_picker('Hintergrund hinter dem Logo', key='avatar_bg',
                            help='Standard: Weiß, damit transparente SVG/PNG-Logos korrekt dargestellt werden.')
        with c2:
            st.color_picker('Fallback-Avatarfarbe (Initialen)', key='color')
        st.radio('Darstellung im Kreis', ['Eingepasst', 'Füllend'], key='avatar_fit', horizontal=True,
                 help='Eingepasst: ganzes Logo sichtbar. Füllend: Kreis wird komplett ausgefüllt (Ränder werden beschnitten).')
        st.slider('Innenabstand (%)', 0, 30, key='avatar_pad', step=2)
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


# ---------------------------------------------------------------------------
# Smartphone-Mockups (344 x 701 px) – drei Geräte: 1 ohne trustedDialog, 2 mit trustedDialog, 3 mit trustedDialog Preview
# ---------------------------------------------------------------------------
# Maße 1:1 aus der Vorlage (344 x 701 px). Koordinaten im .screen relativ zur linken oberen Display-Ecke.
# Grundlinien (Baseline) der Texte stammen aus der Vorlage; top = Baseline - 0,842 x Schriftgröße (Roboto, line-height 1).
# Header (Status-Leiste, Kopfzeile, Suche) und Footer (Navigation, Home-Indikator) sind für alle drei Geräte identisch.
BOARD_W, BOARD_H = 1144, 785          # Vergleichsgrafik: 3 x 344 px + 2 x 36 px Abstand + 20 px Rand; Titel + Gerät + Rand
TD_ROW_TOP = 134                      # Oberkante der ersten Mail (unterhalb der Trennlinie)
TD_ROW_H_PREVIEW = 169                # Zeilenhöhe der ersten Mail mit tD-Preview-Grafik (wie bisher)
TD_ROW_H_PLAIN = 68.5                 # Zeilenhöhe der ersten Mail ohne Preview-Grafik (gleiche Abstände wie die übrigen Mails)
ROW_SHIFT = TD_ROW_H_PREVIEW - TD_ROW_H_PLAIN   # um so viel rücken die weiteren Mails bei Gerät 1 und 2 nach oben

PHONE_CSS = r'''<style>
*{box-sizing:border-box;margin:0;padding:0}
html,body{height:100%;overflow:hidden;background:transparent;font-family:Roboto,"Helvetica Neue",Arial,sans-serif;-webkit-font-smoothing:antialiased}
.wrap{display:flex;flex-direction:column;align-items:center;height:100%}
#fitbox{position:relative;flex:0 0 auto;overflow:hidden;border-radius:8px;box-shadow:0 0 0 1px rgba(128,128,128,.28)}
#scaler{position:absolute;left:0;top:0;transform-origin:0 0}
#board{position:relative;width:__BW__px;height:__BH__px;background:#fff;display:flex;justify-content:center;align-items:flex-start;gap:36px;padding:20px 20px 0}
.col{display:flex;flex-direction:column;align-items:center;gap:10px}
.ptitle{height:34px;font:400 24px/34px Roboto,"Helvetica Neue",Arial,sans-serif;color:#111;white-space:nowrap}
.toolbar{flex:0 0 auto;display:flex;gap:10px;justify-content:center;padding-top:10px}
.phonewrap{position:relative;width:344px;height:701px}
.sidebtn{position:absolute;border:1px solid #2c2b29;border-radius:1.5px;background:linear-gradient(90deg,#9a9895,#dcdbd9 50%,#b3b1ae)}
.phone{position:absolute;left:7.5px;top:6.5px;width:325px;height:688px;border-radius:55px;background:#1b1a18}
.l1,.l2,.l3,.bezel{position:absolute}
.l1{inset:2px;border-radius:53px;background:#f1f1f1}
.l2{inset:3px;border-radius:52px;background:#a4a4a4}
.l3{inset:4px;border-radius:51px;background:#3f3f3f}
.bezel{inset:5.5px;border-radius:49.5px;background:#100f0d}
.screen{position:absolute;left:13.5px;top:12.5px;width:297.5px;height:662.5px;overflow:hidden;border-radius:42px;background:#fff;color:#111}
.abs{position:absolute}
.t{position:absolute;line-height:1;white-space:nowrap}
/* Status-Leiste */
.time{left:21.5px;top:12.2px;font:600 15px/1 Inter,-apple-system,"SF Pro Text",Roboto,Arial,sans-serif;color:#000;letter-spacing:-1px}
.island{left:112px;top:12px;width:75px;height:22px;border-radius:11px;background:#0c0c0c}
.island i{position:absolute;left:60.5px;top:7px;width:8px;height:8px;border-radius:50%;background:radial-gradient(circle,#0a0a2a 25%,#26357a 60%,#121212 100%)}
.signal{left:213px;top:14px;width:18px;height:11px}
.wifi{left:236px;top:14.5px;width:13px;height:9.5px}
.battery{left:254px;top:15px;width:21.5px;height:10.5px;border-radius:3.5px;background:#111;color:#fff;font:700 8.4px/10.5px Inter,-apple-system,Roboto,Arial,sans-serif;text-align:center;letter-spacing:-.1px}
.battip{left:276.3px;top:18.3px;width:1.6px;height:4px;border-radius:0 1px 1px 0;background:#c8c8c8}
/* Kopfzeile */
.round{width:35px;height:35px;top:45px;border-radius:50%;background:#fff;box-shadow:0 0 10px rgba(0,0,0,.065);display:flex;align-items:center;justify-content:center}
.hicon{stroke:#111;fill:none;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}
.title{left:49.5px;top:51.5px;font:700 12.5px/1 Roboto,Arial,sans-serif;color:#000}
.mail{left:49.5px;top:64.6px;font:400 10px/1 Roboto,Arial,sans-serif;color:#a2a2a2}
.search{left:5px;top:89px;width:284px;height:32px;border-radius:16px;background:#fdfdfd;box-shadow:0 0 10px rgba(0,0,0,.06)}
.search .sicon{position:absolute;left:10px;top:10px;width:12px;height:12px}
.signal svg,.wifi svg,.sicon svg,.navicon svg{display:block}
.search span{left:30px;top:11px;font:400 13px/1 Roboto,Arial,sans-serif;color:#6e6e6e}
.sline{left:4px;top:133px;width:286px;height:2px;background:#e8e8e8}
/* Mailliste */
.row{position:absolute;left:0;width:297.5px}
.div{position:absolute;left:17.5px;right:0;bottom:0;height:1px;background:#ececec}
.avatar{position:absolute;left:16.5px;width:33px;height:33px;border-radius:50%;object-fit:cover;display:flex;align-items:center;justify-content:center;color:#fff;font:700 12.5px/33px Roboto,Arial,sans-serif;text-align:center;background:#B8DDFD;overflow:hidden}
.nl{position:absolute;left:59.5px;height:14px;max-width:198px;display:flex;align-items:center;white-space:nowrap}
.sender{font:700 14px/14px Roboto,Arial,sans-serif;color:#000;min-width:0;flex:0 1 auto;overflow:hidden;white-space:nowrap}
.seal{width:13px;height:13px;flex:0 0 13px;margin-left:4.5px;object-fit:contain}
.sj,.pr{position:absolute;left:59.5px;width:204px;height:12.3px;font:400 12.3px/12.3px Roboto,Arial,sans-serif;white-space:nowrap;overflow:hidden}
.sj{color:#151515}
.sj.unread{font-weight:700;color:#000}
.pr{color:#a0a0a0}
.tm{position:absolute;right:9.5px;font:400 9.8px/1 Roboto,Arial,sans-serif;color:#a3a3a3}
.pwrap{position:absolute;left:57px;top:64px;width:216px;height:91px;border-radius:3px;overflow:hidden}
.preview{width:100%;height:100%;object-fit:cover;display:block}
.placeholder{background:#e1002d;color:#fff;display:flex;align-items:center;justify-content:center;font-size:11px}
/* Navigation */
.dock{left:0;top:586px;width:297.5px;height:77px;background:linear-gradient(to bottom,rgba(255,255,255,0) 0,#f4f4f4 17px,#efefef 100%)}
.nav{left:8.5px;top:603px;width:277px;height:48px;border-radius:24px;background:#fff;box-shadow:0 1px 6px rgba(0,0,0,.05)}
.navhl{left:11.5px;top:606px;width:57.5px;height:43px;border-radius:21.5px;background:#eeeeed}
.navicon{position:absolute;top:612px}
.navlabel{position:absolute;top:634.8px;width:60px;margin-left:-30px;text-align:center;font:500 8.6px/1 Roboto,Arial,sans-serif;color:#262626;letter-spacing:-.05px}
.navlabel.active{color:#2f6fbf}
.home{left:100px;top:653px;width:98px;height:4px;border-radius:2px;background:#111}
.downloadbtn{border:1px solid #777;background:#fff;color:#111;border-radius:6px;padding:9px 14px;font:600 13px Arial,sans-serif;cursor:pointer}
.downloadbtn:hover{background:#f4f4f4}
.downloadbtn.primary{background:#1667c7;border-color:#1667c7;color:#fff}
.downloadbtn.primary:hover{background:#1a73dc}
.downloadbtn:disabled{opacity:.6;cursor:wait}
</style>'''

PHONE_OPEN = r'''<div class="phonewrap">
<div class="sidebtn" style="left:4px;top:129px;width:5px;height:22px"></div>
<div class="sidebtn" style="left:4px;top:174px;width:5px;height:44px"></div>
<div class="sidebtn" style="left:4px;top:235px;width:5px;height:44px"></div>
<div class="sidebtn" style="left:331.5px;top:208px;width:6px;height:71px"></div>
<div class="phone"><div class="l1"></div><div class="l2"></div><div class="l3"></div><div class="bezel"></div>
<div class="screen">'''

PHONE_HEAD = r'''<span class="abs time nowtime">09:24</span>
<span class="abs island"><i></i></span>
<span class="abs signal"><svg width="18" height="11" viewBox="0 0 18 11" aria-label="Mobilfunk"><rect x="1.2" y="6.2" width="2.7" height="4.5" rx=".7" fill="#111"/><rect x="5.8" y="4.7" width="2.7" height="6" rx=".7" fill="#c6c6c6"/><rect x="10.4" y="2.9" width="2.7" height="7.8" rx=".7" fill="#c6c6c6"/><rect x="15" y="1" width="2.7" height="9.7" rx=".7" fill="#c6c6c6"/></svg></span>
<span class="abs wifi"><svg width="13" height="9.5" viewBox="0 0 13 9.5" aria-label="WLAN"><path d="M1 3.6a7.9 7.9 0 0 1 11 0" fill="none" stroke="#c9c9c9" stroke-width="1.7" stroke-linecap="round"/><path d="M3.1 5.7a4.9 4.9 0 0 1 6.8 0" fill="none" stroke="#000" stroke-width="1.7" stroke-linecap="round"/><path d="M6.5 9.1 4.9 7.5a2.3 2.3 0 0 1 3.2 0z" fill="#000" stroke="#000" stroke-width=".9" stroke-linejoin="round"/></svg></span>
<span class="abs battery">93</span><span class="abs battip"></span>
<span class="abs round" style="left:3px"><svg class="hicon" width="16" height="16" viewBox="0 0 16 16"><path d="M11 1.6 4.6 8l6.4 6.4"/></svg></span>
<span class="t title">Posteingang</span><span class="t mail">trusteddialog99@gmx.net</span>
<span class="abs round" style="left:210.5px"><svg class="hicon" width="18" height="18" viewBox="0 0 18 18" style="stroke-width:1.7"><circle cx="9" cy="9" r="7.4"/><path d="m5.9 9.2 2.1 2.1 4.1-4.4"/></svg></span>
<span class="abs round" style="left:255px"><svg width="19" height="19" viewBox="0 0 19 19"><path d="M8.5 3.2H4.2A1.7 1.7 0 0 0 2.5 4.9v9.9a1.7 1.7 0 0 0 1.7 1.7h9.9a1.7 1.7 0 0 0 1.7-1.7v-4.3" fill="none" stroke="#111" stroke-width="2" stroke-linecap="round"/><path d="M14.6 1.7a1.6 1.6 0 0 1 2.3 2.3l-7.2 7.2-3.2.9.9-3.2z" fill="#111"/></svg></span>
<div class="abs search"><span class="sicon"><svg width="12" height="12" viewBox="0 0 12 12"><circle cx="5" cy="5" r="4" fill="none" stroke="#111" stroke-width="1.6"/><path d="m8 8 3.2 3.2" stroke="#111" stroke-width="1.7" stroke-linecap="round"/></svg></span><span class="t">Suchen</span></div>
<span class="abs sline"></span>'''

PHONE_FOOT = r'''<div class="abs dock"></div>
<div class="abs nav"></div><div class="abs navhl"></div>
<span class="navicon" style="left:31px;top:614px"><svg width="18" height="15" viewBox="0 0 18 15"><rect width="18" height="15" fill="#1667c7"/><path d="M.6 .9 9 8l8.4-7.1M.6 14.2l6.3-6.6M17.4 14.2l-6.3-6.6" fill="none" stroke="#fff" stroke-width="1.15"/></svg></span>
<span class="navicon" style="left:86px;top:615px"><svg width="16.5" height="13.5" viewBox="0 0 18 13.5" preserveAspectRatio="none"><path d="M0 1.3C0 .6.5 0 1.2 0h4.7l1.7 1.9h9.2c.7 0 1.2.6 1.2 1.3v9c0 .7-.5 1.3-1.2 1.3H1.2C.5 13.5 0 12.9 0 12.2z" fill="#111"/></svg></span>
<span class="navicon" style="left:135px;top:613px"><svg width="21" height="19" viewBox="0 0 21 19"><path d="M1.2 5.2v11.6c0 .6.5 1.1 1.1 1.1h11.8" fill="none" stroke="#111" stroke-width="1.8" stroke-linecap="round"/><rect x="4.6" y=".3" width="15.6" height="14.4" rx="1.3" fill="#111"/><path d="m7.3 11.6 3.1-3.6 2 2.2 1.8-2 3 3.4z" fill="#fff"/><circle cx="16" cy="4.5" r="1.3" fill="#fff"/></svg></span>
<span class="navicon" style="left:193px;top:617px"><svg width="15" height="11" viewBox="0 0 15 11"><rect x="0" y="7.2" width="2.4" height="3.8" rx=".5" fill="#222"/><rect x="4.2" y="4.8" width="2.4" height="6.2" rx=".5" fill="#222"/><rect x="8.4" y="2.4" width="2.4" height="8.6" rx=".5" fill="#222"/><rect x="12.6" y="0" width="2.4" height="11" rx=".5" fill="#222"/></svg></span>
<span class="navicon" style="left:243px;top:613px"><svg width="19" height="17" viewBox="0 0 19 17"><rect x="0" y="0" width="19" height="17" rx="1.2" fill="#111"/><path d="M3 2.6v12" stroke="#fff" stroke-width="1"/><rect x="5.3" y="2.7" width="11" height="2.8" fill="none" stroke="#fff" stroke-width=".95"/><path d="M5.3 8.2h4.4M5.3 11.4h4.4" stroke="#fff" stroke-width="1.1"/><rect x="11.4" y="7.4" width="4.9" height="4.8" fill="none" stroke="#fff" stroke-width=".95"/></svg></span>
<span class="navlabel active" style="left:40.5px">E-Mail</span>
<span class="navlabel" style="left:93.5px">Dateien</span>
<span class="navlabel" style="left:146.5px">Fotos</span>
<span class="navlabel" style="left:200.5px">Mobile</span>
<span class="navlabel" style="left:252.5px">News</span>
<div class="abs home"></div>'''

PHONE_CLOSE = '</div></div></div>'

TD_ROW = r'''<div class="row" style="top:134px;height:__H__px">__AV__<div class="nl" style="top:9.2px"><span class="sender fit">__SENDER__</span>__SEAL__</div><div class="tm" style="top:10.7px" data-off="-3"></div><div class="sj unread fit" style="top:27.6px">__SUBJECT__</div><div class="pr fit" style="top:44.6px">__PRE__</div>__PVBLOCK__<div class="div"></div></div>'''

OTHER_ROWS = r'''<div class="row" style="top:__T1__px;height:58.5px"><span class="avatar" style="top:10px">OH</span><div class="nl" style="top:15.2px"><span class="sender">Otto Holler</span></div><div class="tm" style="top:14.7px" data-off="-23"></div><div class="sj" style="top:33.6px">Gewünschte Bilder</div><div class="div"></div></div>
<div class="row" style="top:__T2__px;height:72px"><span class="avatar" style="top:9.5px">FF</span><div class="nl" style="top:12.7px"><span class="sender">Fred Fritt</span></div><div class="tm" style="top:15.2px" data-off="-69"></div><div class="sj" style="top:30.1px">Klassentreffen</div><div class="pr" style="top:48.1px">Schön war es!</div><div class="div"></div></div>
<div class="row" style="top:__T3__px;height:72.5px"><img class="avatar" style="top:9.5px;background:#1d72e8" src="__GMXLOGO__" alt="GMX"><div class="nl" style="top:13.7px"><span class="sender">GMX Magazin</span>__SEAL__</div><div class="tm" style="top:15.2px" data-off="-117"></div><div class="sj fit" style="top:31.1px">Traumhaus auf Föhr zu gewinnen: 8 Zimmer, Meerblick</div><div class="pr fit" style="top:49.1px">Jetzt Lose bei GMX Lotto sichern! Wer jetzt mitspielt …</div><div class="div"></div></div>
<div class="row" style="top:__T4__px;height:72px"><span class="avatar" style="top:8px">SW</span><div class="nl" style="top:13.2px"><span class="sender">Shopping World</span></div><div class="tm" style="top:14.7px" data-off="-145"></div><div class="sj" style="top:30.6px">Neue Deals am Wochenende</div><div class="pr" style="top:47.6px">Jetzt entdecken</div><div class="div"></div></div>'''

BOARD_TEMPLATE = r'''<!doctype html><html><head><meta charset="utf-8">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Roboto:wght@400;500;700&family=Inter:wght@600;700&display=swap">
<script src="https://cdn.jsdelivr.net/npm/html2canvas@1.4.1/dist/html2canvas.min.js"></script>__CSS__</head><body><div class="wrap">
<div id="fitbox"><div id="scaler"><div id="board">
<div class="col" id="col1"><div class="ptitle">Ohne trustedDialog</div>__PHONE1__</div>
<div class="col" id="col2"><div class="ptitle">Mit trustedDialog</div>__PHONE2__</div>
<div class="col" id="col3"><div class="ptitle">Mit trustedDialog Preview</div>__PHONE3__</div>
</div></div></div>
<div class="toolbar" id="toolbar"><button class="downloadbtn primary" onclick="downloadBoard(this)">Alle 3 Mockups als eine PNG-Grafik herunterladen</button><button class="downloadbtn" onclick="downloadPhone(this)">Nur Mockup 3 (mit Preview)</button></div>
</div>
<script>
const BOARD_W=__BW__,BOARD_H=__BH__;
const p=n=>String(n).padStart(2,'0'),fmt=d=>p(d.getHours())+':'+p(d.getMinutes());
function tick(){let n=new Date();document.querySelectorAll('.nowtime').forEach(x=>x.textContent=fmt(n));document.querySelectorAll('[data-off]').forEach(x=>x.textContent=fmt(new Date(n.getTime()+Number(x.dataset.off)*60000)))}
tick();setInterval(tick,30000);
/* Zu lange Texte pixelgenau mit „…“ kürzen (wie in der GMX-App). Beim Absender bleibt das Siegel dadurch immer sichtbar. */
function fitText(el){
 if(el.dataset.full===undefined) el.dataset.full=el.textContent;
 const full=el.dataset.full; el.textContent=full;
 const fits=()=>el.scrollWidth<=el.clientWidth+.5;
 if(fits()) return;
 let lo=0,hi=full.length;
 while(lo<hi){const mid=(lo+hi+1)>>1;el.textContent=full.slice(0,mid).trimEnd()+'…';if(fits()) lo=mid; else hi=mid-1;}
 el.textContent=full.slice(0,lo).trimEnd()+'…';
}
function fitAll(){document.querySelectorAll('.fit').forEach(fitText)}
fitAll();
if(document.fonts&&document.fonts.ready) document.fonts.ready.then(fitAll);
/* Avatar der tD-Mails (Gerät 2 und 3): SVG/PNG auf den gewählten Hintergrund (Standard Weiß) legen und als PNG fixieren. */
async function rasterizeTdAvatar(img){
 const source=new Image();
 await new Promise((resolve,reject)=>{source.onload=resolve;source.onerror=reject;source.src=img.dataset.src;});
 const size=264,canvas=document.createElement('canvas');canvas.width=size;canvas.height=size;
 const ctx=canvas.getContext('2d');
 ctx.fillStyle=img.dataset.bg||'#ffffff';ctx.fillRect(0,0,size,size);
 const pad=size*Math.max(0,Math.min(.4,Number(img.dataset.pad)||0)),inner=size-2*pad;
 const sw=source.naturalWidth||size,sh=source.naturalHeight||size;
 const scale=img.dataset.fit==='cover'?Math.max(inner/sw,inner/sh):Math.min(inner/sw,inner/sh);
 const dw=sw*scale,dh=sh*scale;
 ctx.imageSmoothingQuality='high';
 ctx.drawImage(source,(size-dw)/2,(size-dh)/2,dw,dh);
 img.style.padding='0';img.style.objectFit='cover';
 img.src=canvas.toDataURL('image/png');
}
(async()=>{for(const img of document.querySelectorAll('img.td-avatar')){try{await rasterizeTdAvatar(img);}catch(err){console.warn('Avatar konnte nicht in PNG umgewandelt werden',err);}}})();
/* Die drei Geräte werden immer komplett in den sichtbaren Bereich eingepasst (nur die Anzeige wird skaliert, nie der Export). */
function fitBoard(){
 const box=document.getElementById('fitbox'),scaler=document.getElementById('scaler'),bar=document.getElementById('toolbar');
 const availW=document.documentElement.clientWidth,availH=window.innerHeight-bar.offsetHeight-6;
 const s=Math.max(.2,Math.min(1,availW/BOARD_W,availH/BOARD_H));
 scaler.style.transform='scale('+s+')';
 box.style.width=Math.round(BOARD_W*s)+'px';box.style.height=Math.round(BOARD_H*s)+'px';
}
fitBoard();window.addEventListener('resize',fitBoard);
function safeSender(){return String(__DLSENDER__).trim().replace(/[\\/:*?"<>|]+/g,'_')||'Absender';}
async function exportNode(node,w,h,filename,button,bg){
 const original=button.textContent;
 try{
  button.disabled=true;button.textContent='PNG wird erstellt…';
  if(typeof html2canvas==='undefined') throw new Error('html2canvas konnte nicht geladen werden');
  await document.fonts.ready;fitAll();
  await Promise.all(Array.from(node.querySelectorAll('img')).map(img=>img.complete ? Promise.resolve() : new Promise(resolve=>{img.onload=resolve;img.onerror=resolve;})));
  const canvas=await html2canvas(node,{
   backgroundColor:bg,
   scale:3,
   useCORS:true,
   allowTaint:false,
   logging:false,
   width:w,
   height:h,
   windowWidth:BOARD_W,
   windowHeight:BOARD_H,
   scrollX:0,
   scrollY:0,
   onclone:(doc)=>{
    /* Export immer in voller Größe, unabhängig von der Skalierung der Anzeige */
    const box=doc.getElementById('fitbox'),scaler=doc.getElementById('scaler');
    scaler.style.transform='none';
    box.style.width=BOARD_W+'px';box.style.height=BOARD_H+'px';box.style.overflow='visible';box.style.boxShadow='none';box.style.borderRadius='0';
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
     img.style.width='33px';img.style.height='33px';
     img.style.minWidth='33px';img.style.minHeight='33px';
     img.style.maxWidth='33px';img.style.maxHeight='33px';
     img.style.borderRadius='50%';img.style.objectFit='cover';
     img.style.objectPosition='center center';img.style.display='block';img.style.visibility='visible';
    });
   }
  });
  const blob=await new Promise(resolve=>canvas.toBlob(resolve,'image/png'));
  if(!blob) throw new Error('PNG-Blob konnte nicht erzeugt werden');
  const url=URL.createObjectURL(blob);
  const link=document.createElement('a');
  link.download=filename;
  link.href=url;
  document.body.appendChild(link);link.click();link.remove();
  setTimeout(()=>URL.revokeObjectURL(url),1000);
 }catch(err){
  console.error(err);
  alert('Die PNG-Datei konnte nicht erzeugt werden: '+err.message);
 }finally{button.disabled=false;button.textContent=original;}
}
function downloadBoard(button){return exportNode(document.getElementById('board'),BOARD_W,BOARD_H,'GMX_trustedDialog_Vergleich_'+safeSender()+'.png',button,'#ffffff');}
function downloadPhone(button){return exportNode(document.querySelector('#col3 .phonewrap'),344,701,'GMX_trustedDialogPreview_'+safeSender()+'.png',button,null);}
</script></body></html>'''


def phone_html(avatar, show_seal, show_preview, sender, subject, preheader, preview_block):
    """Ein Gerät. Header und Footer sind in allen drei Varianten identisch; nur die erste Mail unterscheidet sich."""
    seal = f'<img class="seal" src="{SEAL}" alt="trustedDialog Siegel">' if show_seal else ''
    row_h = TD_ROW_H_PREVIEW if show_preview else TD_ROW_H_PLAIN
    shift = 0 if show_preview else ROW_SHIFT
    first = (TD_ROW.replace('__H__', f'{row_h:g}').replace('__AV__', avatar).replace('__SEAL__', seal)
             .replace('__SENDER__', sender).replace('__SUBJECT__', subject).replace('__PRE__', preheader)
             .replace('__PVBLOCK__', preview_block if show_preview else ''))
    rest = OTHER_ROWS.replace('__GMXLOGO__', GMX_LOGO).replace('__SEAL__', f'<img class="seal" src="{SEAL}" alt="trustedDialog Siegel">')
    for token, top in (('__T1__', 303), ('__T2__', 361.5), ('__T3__', 433.5), ('__T4__', 506)):
        rest = rest.replace(token, f'{top - shift:g}')
    return PHONE_OPEN + PHONE_HEAD + first + rest + PHONE_FOOT + PHONE_CLOSE


def build_board_html(sender_name, subject_text, preheader_text, avatar_src='', avatar_bg=AVATAR_BG_DEFAULT,
                     avatar_fit='contain', avatar_pad=0.0, fallback_color=AVATAR_DEFAULT, preview_src=''):
    """Erzeugt die Gegenüberstellung der drei GMX-Smartphone-Mockups (HTML) für die Live-Vorschau und den PNG-Export.
    Alle drei Geräte erhalten dieselben Texte (Absender/Marke, Betreff, Preview-Text)."""
    bg = e(avatar_bg or AVATAR_BG_DEFAULT)
    letters = e(''.join(x[0] for x in (sender_name or '').split()[:2]).upper() or 'M')
    initials = f'<span class="avatar" style="top:6px;background:{e(fallback_color)}">{letters}</span>'
    if avatar_src:
        fit = 'cover' if avatar_fit == 'cover' else 'contain'
        pad_px = round(33 * avatar_pad, 2)
        logo = (f'<img class="avatar td-avatar" style="top:6px;background:{bg};object-fit:{fit};padding:{pad_px}px" '
                f'src="{avatar_src}" data-src="{avatar_src}" data-bg="{bg}" data-fit="{fit}" data-pad="{avatar_pad}" alt="">')
    else:
        logo = initials
    pv = f'<img class="preview" src="{preview_src}">' if preview_src else '<div class="preview placeholder">Bild einfügen</div>'
    preview_block = f'<div class="pwrap">{pv}</div>'
    texts = (display_text(sender_name) or 'Marke', display_text(subject_text), display_text(preheader_text))
    download_sender = json.dumps(sender_name or 'Absender', ensure_ascii=False).replace('<', '\\u003c')
    phones = (
        phone_html(initials, False, False, *texts, preview_block),   # 1. ohne trustedDialog: Initialen-Avatar, kein Siegel
        phone_html(logo, True, False, *texts, preview_block),        # 2. mit trustedDialog: Logo-Avatar + Siegel
        phone_html(logo, True, True, *texts, preview_block),         # 3. mit trustedDialog Preview: zusätzlich Preview-Grafik
    )
    out = BOARD_TEMPLATE.replace('__CSS__', PHONE_CSS)
    for token, value in {'__PHONE1__': phones[0], '__PHONE2__': phones[1], '__PHONE3__': phones[2],
                         '__BW__': str(BOARD_W), '__BH__': str(BOARD_H), '__DLSENDER__': download_sender}.items():
        out = out.replace(token, value)
    return out


if af:
    uploaded = avatar_data_uri(af.getvalue())
    avatar_src = uploaded[0] if uploaded else uri(af)
elif st.session_state.avatar_options and 0 <= st.session_state.avatar_choice < len(st.session_state.avatar_options):
    avatar_src = st.session_state.avatar_options[st.session_state.avatar_choice]['src']
else:
    avatar_src = ''
psrc = uri(pf) if pf else ('data:image/png;base64,' + base64.b64encode(st.session_state.generated_preview).decode()
                           if st.session_state.generated_preview else '')
H = build_board_html(st.session_state.sender, st.session_state.subject, st.session_state.preheader, avatar_src,
                     st.session_state.avatar_bg, 'cover' if st.session_state.avatar_fit == 'Füllend' else 'contain',
                     st.session_state.avatar_pad / 100, st.session_state.color, psrc)
with right:
    # Rechte Spalte bleibt beim Scrollen der Eingabefelder stehen (sticky) und ist so hoch wie der sichtbare Bereich.
    # Die Anzeige skaliert die drei Geräte automatisch in diese Fläche; der PNG-Export bleibt immer in voller Größe.
    st.markdown(STICKY_CSS, unsafe_allow_html=True)
    html_component = getattr(components, 'html', None)   # in neueren Streamlit-Versionen abgekündigt
    if html_component is not None:
        html_component(H, height=800, scrolling=False)
    else:
        st.iframe(H, height=800)
st.caption('Echtes trustedDialog SVG-Siegel · Avatar-Auswahl aus der Website · Live-Zeit mit früheren Mailzeiten · '
           'Maße nach GMX-App-Vorlage (je Gerät 344 × 701 px) · Export: eine Grafik mit allen 3 Mockups')
