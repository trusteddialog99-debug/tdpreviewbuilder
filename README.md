# trustedDialog Preview Builder - HTML/CSS MVP

Diese Version rendert das GMX/iOS-Mockup als echte HTML/CSS-Komponente innerhalb von Streamlit. Pillow wird nicht mehr für die Live-Vorschau verwendet.

## Dateien für GitHub

- `app.py`
- `requirements.txt`
- `README.md`

## Start

```powershell
pip install -r requirements.txt
streamlit run app.py
```

## Enthalten

- getrennte Streamlit-Eingaben und Preview-Komponente
- stabile CSS-Zeilenhöhen und Abstände
- dynamischer Avatar oder Initialen-Fallback
- dynamisches Preview-Bild
- GMX/iOS-Ansicht mit weiteren Inbox-Einträgen
- Vollbild-Schaltfläche
