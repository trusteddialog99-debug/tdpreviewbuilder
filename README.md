# trustedDialog Preview Builder

Ein Streamlit-MVP für eine editierbare trustedDialog Preview mit WEB.DE-Mobile-Mockup.

## Funktionen

- Domainanalyse mit Erkennung von Markenname, Angebots-Hinweisen, Logo- und Bildkandidaten
- manuell editierbare Vorschläge für Absender, Betreff, Vorschautext und Gutschein
- Avatar-Upload oder automatisch erzeugter Initialen-Avatar
- Preview-Bild-Upload oder Auswahl eines Website-Bildes
- automatischer Zuschnitt auf 1088 x 464 Pixel
- optionale Headline und CTA im Preview-Bild
- WEB.DE-Live-Vorschau
- PNG-Export des vollständigen Mockups und des Preview-Bildes
- grundlegende URL-Sicherheitsprüfung gegen lokale/private Ziele

## Lokal starten

```bash
python -m venv .venv
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

macOS/Linux:

```bash
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## Streamlit Community Cloud

1. `app.py`, `requirements.txt` und optional diese README in ein GitHub-Repository legen.
2. In Streamlit Community Cloud das Repository auswählen.
3. Als Main file path `app.py` eintragen.
4. App deployen.

## Hinweise

- Die Websiteanalyse funktioniert nur für öffentlich erreichbare Websites.
- Manche Websites blockieren automatisierte Abrufe oder laden Inhalte ausschließlich per JavaScript. In diesem Fall bleiben Upload und manuelle Bearbeitung verfügbar.
- Der MVP verwendet keine externe KI-API. Textvorschläge werden regelbasiert aus den erkannten Informationen erzeugt. Eine LLM-Anbindung kann später als Backend-Service ergänzt werden.
- Logos und Bilder dürfen nur verwendet werden, wenn die erforderlichen Nutzungsrechte vorliegen.
- Die Darstellung ist ein Mockup und keine technische Freigabe für den produktiven Versand.
