import base64
import html
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="trustedDialog Preview Builder", page_icon="✉️", layout="wide")


def data_uri(uploaded_file):
    if uploaded_file is None:
        return ""
    mime = uploaded_file.type or "image/png"
    encoded = base64.b64encode(uploaded_file.getvalue()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def initial_letters(value):
    parts = [part for part in value.strip().split() if part]
    return "".join(part[0] for part in parts[:2]).upper() or "M"


def esc(value):
    return html.escape(value or "", quote=True)


DEFAULTS = {
    "sender": "Marke",
    "subject": "Betreff",
    "preheader": "Preview",
    "avatar_color": "#8EA8CE",
}
for key, value in DEFAULTS.items():
    st.session_state.setdefault(key, value)

st.title("trustedDialog Preview Builder")
st.caption("HTML/CSS-MVP nach der Konfigurator- und Preview-Logik des UIM Ad Managers")

form_col, preview_col = st.columns([0.86, 1.14], gap="large")

with form_col:
    st.subheader("Inhalte")
    st.text_input("Absender / Marke", key="sender", max_chars=29)
    st.caption(f"{len(st.session_state.sender)}/29 Zeichen")
    st.text_input("Betreff", key="subject", max_chars=29)
    st.caption(f"{len(st.session_state.subject)}/29 Zeichen")
    st.text_input("Preview-Text", key="preheader", max_chars=29)
    st.caption(f"{len(st.session_state.preheader)}/29 Zeichen")
    st.color_picker("Fallback-Avatarfarbe", key="avatar_color")
    avatar_file = st.file_uploader("Avatar / Logo", type=["png", "jpg", "jpeg", "webp"])
    preview_file = st.file_uploader("Preview-Bild 1088 × 464 px", type=["png", "jpg", "jpeg", "webp"])
    st.info("Das Mockup wird jetzt als echte HTML/CSS-Komponente gerendert. Dadurch bleiben Zeilenhöhen, Abstände und Textfluss stabil.")

sender = esc(st.session_state.sender)
subject = esc(st.session_state.subject)
preheader = esc(st.session_state.preheader)
avatar_color = esc(st.session_state.avatar_color)
avatar_src = data_uri(avatar_file)
preview_src = data_uri(preview_file)
initials = esc(initial_letters(st.session_state.sender))

avatar_html = (
    f'<img class="avatar-image" src="{avatar_src}" alt="Avatar">'
    if avatar_src
    else f'<span class="avatar-fallback" style="background:{avatar_color}">{initials}</span>'
)
preview_html = (
    f'<img class="td-preview-image" src="{preview_src}" alt="trustedDialog Preview">'
    if preview_src
    else '<div class="td-preview-placeholder">Bild einfügen</div>'
)

component_html = f"""
<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  :root {{
    --phone-width: 390px;
    --phone-height: 780px;
    --screen-left: 14px;
    --screen-top: 14px;
    --screen-width: 362px;
    --screen-height: 752px;
    --blue: #1688e8;
    --line: #dedede;
    --muted: #9b9b9b;
    --text: #111111;
  }}
  * {{ box-sizing: border-box; }}
  html, body {{ margin: 0; padding: 0; background: transparent; font-family: Arial, Helvetica, sans-serif; }}
  .stage {{ display: flex; flex-direction: column; align-items: center; width: 100%; padding: 2px 0 14px; }}
  .phone {{
    position: relative;
    width: var(--phone-width);
    height: var(--phone-height);
    border-radius: 58px;
    background: #111;
    border: 2px solid #777;
    box-shadow: inset 0 0 0 2px #d4d4d4, 0 8px 22px rgba(0,0,0,.18);
  }}
  .phone::before {{
    content: "";
    position: absolute;
    inset: 5px;
    border: 1px solid #2d2d2d;
    border-radius: 53px;
    pointer-events: none;
    z-index: 20;
  }}
  .side-button {{ position:absolute; background:#343434; border-radius:3px; }}
  .side-button.left.one {{ left:-5px; top:124px; width:4px; height:61px; }}
  .side-button.left.two {{ left:-5px; top:202px; width:4px; height:88px; }}
  .side-button.right {{ right:-5px; top:205px; width:4px; height:112px; }}
  .screen {{
    position: absolute;
    left: var(--screen-left);
    top: var(--screen-top);
    width: var(--screen-width);
    height: var(--screen-height);
    overflow: hidden;
    background: #fff;
    border-radius: 46px;
    color: var(--text);
  }}
  .status {{ position:relative; height:43px; padding:14px 24px 0; font-size:13px; font-weight:700; }}
  .island {{ position:absolute; top:10px; left:50%; transform:translateX(-50%); width:106px; height:31px; border-radius:18px; background:#090909; }}
  .status-icons {{ position:absolute; right:20px; top:14px; letter-spacing:2px; font-size:11px; }}
  .app-header {{ height:60px; display:grid; grid-template-columns:38px 1fr 40px 40px; align-items:center; gap:5px; padding:0 14px; }}
  .icon-circle {{ width:36px; height:36px; display:flex; align-items:center; justify-content:center; border-radius:50%; background:#fafafa; font-weight:700; font-size:24px; }}
  .heading strong {{ display:block; font-size:14px; line-height:17px; }}
  .heading small {{ display:block; font-size:10px; color:#a3a3a3; line-height:12px; }}
  .search {{ height:42px; margin:0 17px 12px; border-radius:22px; background:#f4f4f5; display:flex; align-items:center; padding:0 16px; color:#777; font-size:15px; }}
  .search-symbol {{ font-size:19px; color:#222; margin-right:10px; }}
  .receive {{ height:34px; border-top:1px solid var(--line); border-bottom:1px solid var(--line); display:flex; align-items:center; gap:14px; padding:0 17px; color:#777; font-size:11px; }}
  .receive-dots {{ color:#5caee9; letter-spacing:3px; font-size:16px; font-weight:700; }}
  .mail-list {{ margin:0 17px; }}
  .mail-row {{ position:relative; display:grid; grid-template-columns:42px minmax(0,1fr) 42px; column-gap:10px; border-bottom:1px solid var(--line); padding:10px 0 9px; }}
  .mail-row.td {{ min-height:244px; padding-top:11px; }}
  .avatar-slot {{ grid-column:1; width:38px; height:38px; }}
  .avatar-image, .avatar-fallback {{ width:38px; height:38px; border-radius:50%; display:flex; align-items:center; justify-content:center; object-fit:cover; color:#fff; font-size:13px; font-weight:700; }}
  .mail-content {{ grid-column:2; min-width:0; }}
  .sender-line {{ height:18px; display:flex; align-items:center; min-width:0; white-space:nowrap; }}
  .sender {{ font-size:13px; line-height:18px; font-weight:700; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; max-width:166px; }}
  .seal {{ width:16px; height:16px; flex:0 0 16px; margin-left:4px; border-radius:50%; background:#278ad2; color:#fff; display:inline-flex; align-items:center; justify-content:center; font-size:11px; line-height:16px; font-weight:700; }}
  .subject {{ height:18px; font-size:13px; line-height:18px; overflow:hidden; white-space:nowrap; text-overflow:ellipsis; }}
  .preheader {{ height:18px; font-size:13px; line-height:18px; color:#aaa; overflow:hidden; white-space:nowrap; text-overflow:ellipsis; }}
  .time {{ grid-column:3; grid-row:1; align-self:start; padding-top:2px; text-align:right; color:#aaa; font-size:10px; line-height:16px; }}
  .preview-wrap {{ grid-column:2 / 4; margin-top:8px; width:253px; height:108px; border-radius:6px; overflow:hidden; }}
  .td-preview-image, .td-preview-placeholder {{ display:block; width:100%; height:100%; object-fit:cover; }}
  .td-preview-placeholder {{ background:#ff00e8; color:#fff; display:flex; align-items:center; justify-content:center; font-size:11px; }}
  .standard {{ min-height:78px; }}
  .standard .avatar-fallback {{ font-size:12px; }}
  .standard .sender {{ max-width:185px; }}
  .standard .subject, .standard .preheader {{ max-width:218px; }}
  .bottom-nav {{ position:absolute; left:16px; right:16px; bottom:13px; height:59px; display:flex; justify-content:space-around; align-items:center; border-radius:31px; background:#fff; box-shadow:0 0 12px rgba(0,0,0,.10); }}
  .nav-item {{ width:53px; text-align:center; color:#111; font-size:9px; line-height:13px; }}
  .nav-icon {{ display:block; font-size:20px; line-height:24px; font-weight:700; }}
  .nav-item.active {{ color:#2687ce; }}
  .badge {{ position:absolute; margin-left:-7px; margin-top:-4px; display:inline-flex; justify-content:center; align-items:center; width:17px; height:17px; border-radius:50%; background:#d6362d; color:white; font-size:10px; }}
  .home {{ position:absolute; bottom:5px; left:50%; transform:translateX(-50%); width:125px; height:4px; border-radius:3px; background:#111; }}
  .actions {{ padding-top:12px; display:flex; gap:8px; justify-content:center; }}
  .actions button {{ border:1px solid #999; background:#fff; border-radius:4px; padding:8px 12px; font:600 12px Arial; cursor:pointer; }}
  @media (max-width: 450px) {{ .phone {{ transform:scale(.92); transform-origin:top center; margin-bottom:-62px; }} }}
</style>
</head>
<body>
<div class="stage">
  <div class="phone" id="phone">
    <span class="side-button left one"></span><span class="side-button left two"></span><span class="side-button right"></span>
    <div class="screen">
      <div class="status"><span>10:03</span><span class="island"></span><span class="status-icons">••• ◔ ▰</span></div>
      <div class="app-header">
        <span class="icon-circle">‹</span>
        <span class="heading"><strong>Posteingang</strong><small>trusteddialog01@gmx.net</small></span>
        <span class="icon-circle" style="font-size:17px">✓</span>
        <span class="icon-circle" style="font-size:18px">↗</span>
      </div>
      <div class="search"><span class="search-symbol">⌕</span>Suchen</div>
      <div class="receive"><span class="receive-dots">•••</span><span>E-Mails empfangen</span></div>
      <div class="mail-list">
        <div class="mail-row td">
          <div class="avatar-slot">{avatar_html}</div>
          <div class="mail-content">
            <div class="sender-line"><span class="sender">{sender}</span><span class="seal">✓</span></div>
            <div class="subject">{subject}</div>
            <div class="preheader">{preheader}</div>
          </div>
          <div class="time">09:33</div>
          <div class="preview-wrap">{preview_html}</div>
        </div>
        <div class="mail-row standard">
          <div class="avatar-slot"><span class="avatar-fallback" style="background:#8EA8CE">OH</span></div>
          <div class="mail-content"><div class="sender-line"><span class="sender">Otto Holler</span></div><div class="subject">Gewünschte Bilder</div><div class="preheader">Hallo zusammen, anbei findet Ihr die…</div></div><div class="time">09:21</div>
        </div>
        <div class="mail-row standard">
          <div class="avatar-slot"><span class="avatar-fallback" style="background:#187FE6;font-size:10px">GMX</span></div>
          <div class="mail-content"><div class="sender-line"><span class="sender">GMX Magazin</span><span class="seal">✓</span></div><div class="subject">Traumhaus auf Föhr zu gewinnen: 8…</div><div class="preheader">Jetzt Lose bei GMX Lotto sichern! W…</div></div><div class="time">09:02</div>
        </div>
        <div class="mail-row standard" style="border-bottom:none">
          <div class="avatar-slot"><span class="avatar-fallback" style="background:#8EA8CE">SW</span></div>
          <div class="mail-content"><div class="sender-line"><span class="sender">Shopping World</span></div><div class="subject">Neue Deals am Wochenende</div><div class="preheader">Jetzt entdecken</div></div><div class="time">08:49</div>
        </div>
      </div>
      <div class="bottom-nav">
        <div class="nav-item active"><span class="nav-icon">✉<span class="badge">4</span></span>E-Mail</div>
        <div class="nav-item"><span class="nav-icon">■</span>Dateien</div>
        <div class="nav-item"><span class="nav-icon">▣</span>Fotos</div>
        <div class="nav-item"><span class="nav-icon">✹</span>Vorteile</div>
        <div class="nav-item"><span class="nav-icon">▤</span>News</div>
      </div>
      <div class="home"></div>
    </div>
  </div>
  <div class="actions"><button onclick="document.getElementById('phone').requestFullscreen()">Vollbild anzeigen</button></div>
</div>
</body></html>
"""

with preview_col:
    st.subheader("GMX Live-Vorschau")
    st.caption("Smartphone · GMX.DE · iOS")
    components.html(component_html, height=850, scrolling=False)

st.divider()
st.caption("MVP: Die Preview ist vollständig als HTML/CSS aufgebaut. Der spätere PNG-Export kann auf derselben Komponente ergänzt werden.")
