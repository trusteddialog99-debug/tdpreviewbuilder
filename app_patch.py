"""Targeted updater for the trustedDialog Preview Builder app.py.

Place this file next to the current app.py and run:
    python app_patch.py

The script creates app.before_sender_avatar_fix.py and updates app.py in place.
Only sender/brand detection, sender truncation, and avatar colors/backgrounds are changed.
"""
from __future__ import annotations

from pathlib import Path
import py_compile

ROOT = Path(__file__).resolve().parent
APP = ROOT / "app.py"
BACKUP = ROOT / "app.before_sender_avatar_fix.py"

if not APP.exists():
    raise SystemExit("app.py wurde im gleichen Verzeichnis nicht gefunden.")

source = APP.read_text(encoding="utf-8")
original = source


def replace_once(old: str, new: str, label: str) -> None:
    global source
    if old not in source:
        raise SystemExit(f"Abbruch: Erwarteter Codeblock nicht gefunden ({label}). app.py blieb unverändert.")
    source = source.replace(old, new, 1)


# 1) Required fallback colors.
replace_once(
    "AVATAR_DEFAULT = '#8ea8ce'  # Platzhalter-Avatar laut GMX-Vorlage",
    "AVATAR_DEFAULT = '#B8DDFD'  # Fallback-Avatar: hellblauer Hintergrund",
    "AVATAR_DEFAULT",
)

# 2) Sender-specific ellipsis. The full sender remains editable in Streamlit;
# only the compact inbox rendering is shortened so the tD seal remains visible.
replace_once(
    "def display_text(x):\n    return e(x[:34] + '...' if len(x) > 34 else x)\n",
    "def display_text(x):\n"
    "    return e(x[:34] + '...' if len(x) > 34 else x)\n"
    "\n"
    "def display_sender(x, limit=26):\n"
    "    value = re.sub(r'\\s+', ' ', x or '').strip()\n"
    "    return e(value[:limit - 3].rstrip() + '...' if len(value) > limit else value)\n",
    "display_sender",
)

# 3) Brand-name extraction: prefer explicit website brand signals over SEO-heavy page titles.
brand_helpers = '''\ndef _jsonld_brand_names(value):
    names = []
    if isinstance(value, dict):
        kind = value.get('@type', '')
        kinds = kind if isinstance(kind, list) else [kind]
        if any(str(item).lower() in {'organization', 'corporation', 'brand', 'website', 'onlinebusiness'} for item in kinds):
            name = value.get('name') or value.get('legalName')
            if isinstance(name, str) and name.strip():
                names.append(name.strip())
        for item in value.values():
            names.extend(_jsonld_brand_names(item))
    elif isinstance(value, list):
        for item in value:
            names.extend(_jsonld_brand_names(item))
    return names


def extract_brand_name(soup, host, title=''):
    candidates = []
    for key in ('og:site_name', 'application-name', 'apple-mobile-web-app-title'):
        value = meta(soup, key)
        if value:
            candidates.append(value)

    for script in soup.find_all('script', attrs={'type': 'application/ld+json'}):
        try:
            payload = json.loads(script.string or script.get_text() or '')
            candidates.extend(_jsonld_brand_names(payload))
        except Exception:
            pass

    for image in soup.find_all('img'):
        marker = (' '.join(image.get('class', [])) + ' ' + (image.get('id') or '')).lower()
        alt = (image.get('alt') or '').strip()
        if alt and 'logo' in marker:
            candidates.append(alt)

    if title:
        candidates.append(title)
    domain_brand = (host.split('.')[0] if host else '').strip()
    if domain_brand:
        candidates.append(domain_brand)

    generic = {'home', 'homepage', 'startseite', 'online shop', 'onlineshop', 'shop'}
    for candidate in candidates:
        candidate = re.sub(r'\\s+', ' ', candidate or '').strip()
        candidate = re.split(r'\\s*[|–—]\\s*', candidate)[0].strip()
        candidate = re.sub(r'\\s+-\\s+.*$', '', candidate).strip()
        candidate = re.sub(r'^(willkommen bei|welcome to)\\s+', '', candidate, flags=re.I).strip()
        if not candidate or candidate.lower() in generic:
            continue
        if len(candidate) > 60:
            continue
        return candidate

    return domain_brand or host
'''
replace_once(
    "def short(value, limit=37):\n"
    "    value = re.sub(r'\\s+', ' ', value or '').strip()\n"
    "    return value if len(value) <= limit else value[:limit - 3].rstrip() + '...'\n",
    "def short(value, limit=37):\n"
    "    value = re.sub(r'\\s+', ' ', value or '').strip()\n"
    "    return value if len(value) <= limit else value[:limit - 3].rstrip() + '...'\n"
    + brand_helpers,
    "brand helpers",
)

replace_once(
    "    title = meta(soup, 'og:site_name') or (soup.title.get_text(' ', strip=True) if soup.title else '')\n"
    "    host = (urlparse(final_url).hostname or '').replace('www.', '')\n"
    "    brand = re.split(r'\\s*[|–—]\\s*', title)[0].strip() if title else host.split('.')[0]\n"
    "    brand = re.sub(r'\\s+-\\s+.*$', '', brand).strip() or host\n",
    "    title = meta(soup, 'og:site_name') or (soup.title.get_text(' ', strip=True) if soup.title else '')\n"
    "    host = (urlparse(final_url).hostname or '').replace('www.', '')\n"
    "    brand = extract_brand_name(soup, host, title)\n",
    "brand assignment",
)

# 4) Use sender-specific inbox shortening.
replace_once(
    "sender, subject, pre = display_text(st.session_state.sender), display_text(st.session_state.subject), display_text(st.session_state.preheader)",
    "sender, subject, pre = display_sender(st.session_state.sender), display_text(st.session_state.subject), display_text(st.session_state.preheader)",
    "sender rendering",
)

# 5) Uploaded/generated brand logo: white circular backing in first tD row.
replace_once(
    "av = (f'<img class=\"avatar\" id=\"uploaded-avatar\" data-is-svg=\"{is_svg}\" src=\"{avsrc}\">' if avsrc",
    "av = (f'<img class=\"avatar brand-logo\" id=\"uploaded-avatar\" data-is-svg=\"{is_svg}\" src=\"{avsrc}\">' if avsrc",
    "brand-logo class",
)

# 6) CSS: required fallback palette, explicit ellipsis, white first-mail logo background.
replace_once(
    ".avatar{position:absolute;left:19px;top:10px;width:36px;height:36px;border-radius:50%;object-fit:cover;display:flex;align-items:center;justify-content:center;color:#fff;font:700 13px/36px Roboto,Arial,sans-serif;text-align:center;background:#8ea8ce}\n"
    ".td .avatar{top:11px}\n"
    ".senderline{position:absolute;left:65px;top:11px;height:20px;display:flex;align-items:center;white-space:nowrap}\n"
    ".sender{font:700 14px/20px Roboto,Arial,sans-serif;color:#000;max-width:170px;overflow:hidden;white-space:nowrap}\n",
    ".avatar{position:absolute;left:19px;top:10px;width:36px;height:36px;border-radius:50%;object-fit:cover;display:flex;align-items:center;justify-content:center;color:#1375d7;font:700 13px/36px Roboto,Arial,sans-serif;text-align:center;background:#B8DDFD}\n"
    ".td .avatar{top:11px}\n"
    ".td .avatar.brand-logo{background:#fff}\n"
    ".senderline{position:absolute;left:65px;top:11px;height:20px;display:flex;align-items:center;white-space:nowrap}\n"
    ".sender{font:700 14px/20px Roboto,Arial,sans-serif;color:#000;max-width:158px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}\n",
    "avatar and sender CSS",
)

if source == original:
    raise SystemExit("Es wurden keine Änderungen vorgenommen.")

BACKUP.write_text(original, encoding="utf-8")
APP.write_text(source, encoding="utf-8")
py_compile.compile(str(APP), doraise=True)
print("OK: app.py wurde aktualisiert und syntaktisch geprüft.")
print(f"Backup: {BACKUP.name}")
