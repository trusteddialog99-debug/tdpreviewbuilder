# trustedDialog Preview Builder

Streamlit-App: Domain eingeben → Absender, Betreff, Preview-Text, Avatar und tD-Preview-Grafik werden vorgeschlagen →
Live-Vorschau als Gegenüberstellung von **3 GMX-App-Mockups** (iOS) → Export als **eine** PNG-Grafik.

## Neu in v11

### 1. Abruf langsamer Seiten (z. B. fcbayern.com: „Read timed out“)
- Lesezeit pro Versuch 25 s (vorher 15 s); Gesamtbudget für die Startseite 60 s, für Bilder/Logos je 20 s
  (`FETCH_READ_TIMEOUT`, `PAGE_FETCH_BUDGET`, `IMAGE_FETCH_BUDGET`). Die Header-Varianten aus v10 bleiben erhalten.
- Bei Fehlschlag wird dieselbe Seite zusätzlich **mit bzw. ohne „www.“** abgerufen (`alternate_urls`).
- Kommt die HTML-Seite nur teilweise an (Abbruch mitten im Download), wird der geladene Anfang (ab 30 KB) genutzt –
  Meta-Tags, Logos und Farben stehen fast immer dort.
- Verständliche Meldung statt `HTTPSConnectionPool(…)`. Der Hinweis zum Workaround empfiehlt jetzt den **Quelltext**
  (Strg+U → Strg+A → Strg+C): Damit werden auch Logos, Motive und Farben gefunden, nicht nur Texte.
- Grenze: Antwortet ein Server gar nicht (Geo-/Rechenzentrums-Sperre, Tarpit), hilft nur der Quelltext-Workaround.

### 2. Sprechende Namen bei „Alternatives Website-Motiv“
- Statt Dateinamen: nummerierte Mini-Vorschau aller Motive plus Beschreibung, z. B. „Armbanduhren“, „Frau in Unterwäsche“.
- Namen stammen (in dieser Reihenfolge) aus: **KI-Bildbeschreibung** (optional, s. u.) → Alt-Text → Link-Beschriftung →
  Bildunterschrift → Überschrift im Teaser → Teaser-Text. Dateinamen und IDs werden nie als Beschreibung genutzt.
- Optional per KI: Ist `ANTHROPIC_API_KEY` gesetzt (Streamlit Cloud: *Settings → Secrets*, lokal: Umgebungsvariable), werden
  alle Motive in **einem** Aufruf beschrieben (Modell `claude-haiku-5-5`, per `ANTHROPIC_MODEL` änderbar). Dabei werden
  verkleinerte Kopien der Website-Bilder an die Anthropic-API gesendet. Ohne Schlüssel läuft alles mit den Website-Texten.
- Zusätzlich: srcset/Lazy-Load-Bilder werden erkannt, unbrauchbare (zu kleine/schmale) Bilder ausgeblendet.

### 3. Texte passend zum Motiv, keine Dopplungen
- Betreff, Preview-Text und Headline der Grafik werden aus dem **Teaser des gewählten Motivs** abgeleitet (Angebot oder
  Überschrift im selben Block). Ein Angebot einer anderen Kategorie wird nicht zu einem Motiv gestellt. Fehlt am Motiv ein
  Text, wird neutral formuliert; ein allgemeines Angebot nur bei Motiven ohne eigenen Kontext (z. B. og:image).
- Beim Wechsel des Motivs werden die Texte mitgeführt – von Hand geänderte Felder bleiben unangetastet (Hinweis erscheint).
- Nicht redundant: **dasselbe Motiv in mehreren Größen** wird nur einmal angeboten (Bild-Hash, größere Variante bleibt);
  Motive mit **eingebranntem Text/Preis/Logo** (nur mit KI erkennbar) werden nicht vorausgewählt und mit Warnung markiert.

## Korrektur: Website-Abruf (`safe_fetch`)

- v9 sendete ausschließlich „vollwertige“ Browser-Header (Chrome/Safari inkl. `Sec-Fetch-*`). Bot-Schutz-Systeme wie bei
  zalando.de gleichen das mit dem TLS-Fingerabdruck von Python ab und blockierten dadurch Seiten, die zuvor liefen.
- Jetzt werden vier Header-Varianten nacheinander probiert: **schlicht** → Chrome → Safari → eigener Bot-Name.
  Die erste Variante, die HTTP 200 liefert, gewinnt. So bleibt alles erreichbar, was mit der schlichten Variante lief,
  und Seiten, die volle Browser-Header verlangen (z. B. hm.com), werden weiterhin gelesen.
- Jeder HTTP-Status ab 400 führt zur nächsten Variante (vorher nur 401/403/429/503). Erst wenn alle Varianten scheitern,
  erscheint die Meldung samt Workaround „Seitentext einfügen“. Bei 404 u. Ä. lautet die Meldung „HTTP-Fehler …“ statt „Bot-Schutz“.
- Timeout: 8 s Verbindungsaufbau, 15 s Lesen pro Variante.

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
   - Zeichenanzahl (inkl. Leerzeichen): Beschreibung max. 17, Code max. 25. Bei langen Texten wird die Schrift in der Box automatisch etwas verkleinert.
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
