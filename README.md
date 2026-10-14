# trustedDialog Preview Builder

Streamlit-App: Domain eingeben → Absender, Betreff, Preview-Text, Avatar und tD-Preview-Grafik werden vorgeschlagen →
Live-Vorschau im GMX-App-Mockup (iOS) → Export als PNG.

## Änderungen in dieser Version

### 1. Smartphone-Mockup nach neuer Vorlage (344 × 701 px, 1:1 vermessen)
- Gerät, Rahmen, Seitentasten und Display (297,5 × 662,5 px, Radius 42 px) exakt nach Vorlage.
- **Status-Leiste:** Uhrzeit, Dynamic Island, Mobilfunk-Balken (1 schwarz, 3 grau), WLAN, Batterie als schwarze Pille mit „93“.
- **Kopfzeile:** Posteingang / trusteddialog99@gmx.net, runde Buttons, Suchfeld. „E-Mails empfangen“ entfällt (nicht in der Vorlage).
- **Mailliste:** Position 1 = trustedDialog-Preview, danach 4 Mails wie in der Vorlage
  (Otto Holler, Fred Fritt, GMX Magazin, Shopping World). Zeilenhöhen, Avatar (33 px), Schriftgrößen und Grundlinien
  stammen aus der Vorlage (Abweichung ≤ 1 px).
- **Footer:** 5 Symbole – E-Mail (aktiv), Dateien, Fotos, Mobile, News; Home-Indikator.
- PNG-Export jetzt in 3-facher Auflösung (1032 × 2103 px). Alle Icons sind so aufgebaut, dass html2canvas sie mit exportiert.

### 2. Absender = Markenname
- Neue Markenerkennung (`detect_brand`): og:site_name, application-name, JSON-LD (Organization/Brand/Store),
  Logo-Alt-Texte, Titel-Fragmente und Copyright-Zeile werden gewichtet und gegen die Domain geprüft.
  Slogans wie „Mode online kaufen“ landen dadurch nicht mehr im Absender; Rechtsformen (GmbH, AG …),
  „Online-Shop“ und Domain-Endungen werden entfernt.
- Zu lange Namen werden im Browser **pixelgenau mit „…“ gekürzt**, damit das trustedDialog-Siegel und die Uhrzeit immer
  sichtbar bleiben (gilt auch für Betreff und Preview-Text, wie in der GMX-App).

### 3. Avatare
- Fallback-Avatarfarbe (Initialen): **#B8DDFD**.
- Avatar der trustedDialog-Mail: Hintergrund standardmäßig **Weiß** (einstellbar), damit transparente SVG/PNG-Logos
  korrekt aussehen. SVGs werden im Browser auf diesen Hintergrund gelegt und als PNG fixiert.
- **Auswahl aus gefundenen Grafiken:** App-Icons, Favicons (inkl. SVG/ICO), Web-App-Manifest-Icons, Kachel-Icon,
  JSON-LD-Logo, Logo-Bilder und Inline-SVG-Logos der Seite. Vorschau als Kreis, Auswahl per Liste, „Initialen“ als Option.
- Darstellung im Kreis: „Eingepasst“ (ganzes Logo sichtbar) oder „Füllend“, plus Innenabstand.
- Eigener Upload überschreibt weiterhin die Auswahl.

### Unverändert
- tD-Preview-Grafik (1088 × 464 px), Website-Analyse, Motivauswahl, Markenfarben.

## Hinweis Schriften
Auf Streamlit Community Cloud sorgt `packages.txt` für Roboto/Liberation. Lokal können Schriftdateien in einen Ordner
`fonts/` neben `app.py` gelegt werden (z. B. `Roboto-Black.ttf`).
