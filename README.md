# trustedDialog Preview Builder

Basis: bereitgestellte `app.py`. Unverändert geblieben sind die Avatar-Verarbeitung (SVG -> PNG im Browser),
der PNG-Export-Block für `img.preview` (html2canvas, Skalierung 2) sowie die Feldlängen und Textlogik.

## Änderungen

### 1. Mobile-Device-Mockup (Maße aus der Vorlage 373 x 755 px abgemessen)
- Gerät 344 x 732 px, Display 316 x 706 px, mehrschichtiger Rahmen (Rand, Highlight, Silber, Bezel) und Seitentasten.
- Status-Leiste: Uhrzeit, Dynamic Island mit Linse, vier graue Signalpunkte, WLAN-Symbol, Batterie als Umriss mit Füllung und Pol (vorher: schwarze Pille mit "93").
- Header, Suchfeld, Trennlinien, "E-Mails empfangen" mit drei Punkten: Position und Größe wie in der Vorlage.
- Zeilen: Zeilenhöhe 92,5 px (vorher 78 px), Avatar 36 px, Bildbereich 227 x 96,8 px mit 6 px Radius, Trennlinien ab der Avatarmitte.
- Platzhalter-Avatare in `#8ea8ce` mit weißen Initialen (vorher `#b8ddfd` mit blauen Initialen); der Farbwähler "Fallback-Avatarfarbe" wirkt jetzt tatsächlich.
- Navigation: Pille mit aktivem E-Mail-Tab, rotem Badge und den Einträgen E-Mail, Dateien, Fotos, **Vorteile** (vorher "Mobil"), News; Home-Indikator.
- Weißer Verlauf über der Liste vor der Navigation, wie in der Vorlage.

### 2. tD-Preview-Grafik (1088 x 464 px)
- **Schrift:** robuste Suche nach Roboto/Inter/Liberation/Arial/DejaVu; skalierbarer Fallback. Vorher führte ein falscher Pfad (`liberation2`) ohne DejaVu zur winzigen Bitmap-Schrift.
- **Skalierung:** Text wird nach Breite **und** Höhe des Textfelds eingepasst; Hauptzahl ist immer das größte Element.
- **Supersampling (2x):** glatte Kanten und Schrift.
- **CI:** Markenfarbe aus Logo, `theme-color`, CSS-Variablen und Häufigkeit im Quelltext (graue/weiße Töne ausgeschlossen, ähnliche Töne zusammengefasst). Das Logo der Marke wird in die Grafik gesetzt (weißer Chip, falls es auf der Markenfarbe untergeht), sonst der Markenname.
- **Lesbarkeit:** Textfarbe (weiß/schwarz) nach WCAG-Kontrast zur Markenfarbe, Button invertiert.
- **Komposition:** Textfläche ca. 40 %, Motiv ca. 55-60 %, Motiv mit Fokus-Zuschnitt statt starrer Bildmitte, kein Text auf dem Motiv, ein Button mit gezeichnetem Pfeil.
- **KI-Kennzeichnung:** kleines Overlay "KI-generiert" an der äußeren Motivecke (nur bei generierten Bildern).
- **Botschaft:** erfindet kein "BIS ZU" mehr; erkennt Prozent, Euro, Gratis-Versand, Sale.
- **Bedienung:** Expander "Grafik-Einstellungen" (Headline, CTA, Markenfarbe + erkannte Farben, gespiegelt); die Grafik aktualisiert sich live.
- **Bugfix Motivauswahl:** `og:image` wurde zuvor als String in eine Tupel-Sortierung gemischt und lieferte nur ein einzelnes Zeichen. Transparente PNGs werden auf Weiß gelegt, zu kleine Bilder übersprungen.

## Hinweis Schriften
Auf Streamlit Community Cloud sorgt `packages.txt` für Roboto/Liberation. Lokal können Schriftdateien in einen Ordner `fonts/` neben `app.py` gelegt werden (z. B. `Roboto-Black.ttf`).
