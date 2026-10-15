# trustedDialog Preview Builder

Streamlit-App: Domain eingeben → Absender, Betreff, Preview-Text, Avatar und tD-Preview-Grafik werden vorgeschlagen →
Live-Vorschau als Gegenüberstellung von **3 GMX-App-Mockups** (iOS) → Export als **eine** PNG-Grafik.

## Neu in dieser Version (Feinschliff)

1. **„Schön war es!“ entfernt:** Fred Fritt ist jetzt eine zweizeilige Mail (58,5 px wie Otto Holler); GMX Magazin und
   Shopping World rücken in allen drei Geräten um 13,5 px auf.
2. **Uhrzeit oben links:** 12 px statt 15 px (`.time{…font:600 12px/1 Inter…}`).
3. **Footer:** Navigationsleiste 5 px höher → 7 px Abstand zum Home-Indikator wie in der GMX-App
   (Home-Indikator bleibt an seiner Position).
4. **Promo-Code (Mockup 3):**
   - Die Website-Analyse sucht nach Codes („mit dem Code SALE20“, „Gutscheincode: …“, „Promo-Code „…““, „Rabattcode …“).
     Ein gefundener Code wird direkt unter der Preview-Grafik in Gerät 3 angezeigt.
   - Ohne Fund: Checkbox „Promo-Code einblenden“; Beschreibung und Code sind dann frei editierbar.
   - Darstellung nach Vorlage: „Beschreibung:“ fett (#262626), Code blau (#2A68AE), gepunktete Umrandung #45872F,
     Pillenform 23 px hoch; die Breite passt sich dem Inhalt an.
   - Abstände: 13 px unter der Grafik, 15 px bis zur Trennlinie → die folgenden Mails rücken um 37 px nach unten.
   - Zeichenanzahl nach Vorlage: Beschreibung max. 20 („IhreCodebeschreibung“), Code max. 7 („IhrCode“).
     Längere Codes werden bei der Analyse angezeigt, aber nicht übernommen. Konstanten: `PROMO_LABEL_MAX`, `PROMO_CODE_MAX`.

## Vorherige Version: 3 Mockups

### Gegenüberstellung mit 3 Mobile Devices
| Gerät | Titel | Erste Mail |
|---|---|---|
| 1 | Ohne trustedDialog | Initialen-Avatar (Fallback-Farbe), **kein** Siegel |
| 2 | Mit trustedDialog | Logo-Avatar + trustedDialog-Siegel, keine Preview-Grafik |
| 3 | Mit trustedDialog Preview | wie bisher: Logo-Avatar + Siegel + Preview-Grafik |

- Alle drei Geräte erhalten dieselben Texte: Absender / Marke, Betreff, Preview-Text (Kürzung mit „…“ wie bisher).
- Header (Status-Leiste, Kopfzeile, Suche) und Footer (Navigation, Home-Indikator) sind unverändert und in allen Geräten identisch.
- Anzahl der Mails und Abstände bleiben wie bisher (erste Mail + 4 weitere). Bei Gerät 1 und 2 rücken die Mails auf, weil
  keine Preview-Grafik Platz einnimmt (Zeilenhöhe der ersten Mail: 68,5 px statt 169 px, Konstante `TD_ROW_H_PLAIN`).

### Sticky-Vorschau
- Layout: links Eingaben (Domain, Texte, Avatar, Grafik-Einstellungen), rechts die Vorschau.
- Die rechte Spalte bleibt beim Scrollen im sichtbaren Bereich stehen (`position: sticky`) und ist so hoch wie das Browserfenster.
- Die drei Geräte werden automatisch so skaliert, dass sie komplett sichtbar sind (nur die Anzeige wird skaliert).

### Export
- „Alle 3 Mockups als eine PNG-Grafik herunterladen“: Titel + 3 Geräte auf weißem Hintergrund, 3-fache Auflösung
  (3432 × 2355 px), unabhängig von der Skalierung der Anzeige.
- „Nur Mockup 3 (mit Preview)“: wie bisher das einzelne Gerät, 1032 × 2103 px, transparenter Hintergrund.

### Technische Hinweise
- Die Sticky-Spalte nutzt CSS `:has()` (aktuelle Versionen von Chrome, Edge, Firefox, Safari).
- Der Export nutzt html2canvas (wird per CDN geladen, benötigt Internetzugang im Browser).

## Frühere Änderungen (unverändert gültig)

### Smartphone-Mockup nach Vorlage (344 × 701 px, 1:1 vermessen)
- Gerät, Rahmen, Seitentasten und Display (297,5 × 662,5 px, Radius 42 px) exakt nach Vorlage.
- Status-Leiste: Uhrzeit, Dynamic Island, Mobilfunk-Balken (1 schwarz, 3 grau), WLAN, Batterie als schwarze Pille mit „93“.
- Kopfzeile: Posteingang / trusteddialog99@gmx.net, runde Buttons, Suchfeld.
- Mailliste: Position 1 = trustedDialog-Mail, danach 4 Mails (Otto Holler, Fred Fritt, GMX Magazin, Shopping World).
- Footer: 5 Symbole – E-Mail (aktiv), Dateien, Fotos, Mobile, News; Home-Indikator.

### Absender = Markenname
- Markenerkennung (`detect_brand`): og:site_name, application-name, JSON-LD, Logo-Alt-Texte, Titel-Fragmente und Copyright-Zeile
  werden gewichtet und gegen die Domain geprüft; Rechtsformen, „Online-Shop“ und Domain-Endungen werden entfernt.
- Zu lange Namen werden pixelgenau mit „…“ gekürzt, damit das trustedDialog-Siegel und die Uhrzeit sichtbar bleiben.

### Avatare
- Fallback-Avatarfarbe (Initialen): **#B8DDFD**.
- Avatar der trustedDialog-Mail: Hintergrund standardmäßig **Weiß** (einstellbar), SVGs werden im Browser auf diesen Hintergrund gelegt.
- Auswahl aus gefundenen Grafiken (App-Icons, Favicons, Manifest-Icons, Kachel-Icon, JSON-LD-Logo, Logo-Bilder, Inline-SVG-Logos);
  Darstellung „Eingepasst“ oder „Füllend“, plus Innenabstand. Eigener Upload überschreibt die Auswahl.

### Unverändert
- tD-Preview-Grafik (1088 × 464 px), Website-Analyse, Motivauswahl, Markenfarben.

## Hinweis Schriften
Auf Streamlit Community Cloud sorgt `packages.txt` für Roboto/Liberation. Lokal können Schriftdateien in einen Ordner
`fonts/` neben `app.py` gelegt werden (z. B. `Roboto-Black.ttf`).
