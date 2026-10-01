# trustedDialog Preview Builder - Corrected Preview Export

Diese Version basiert auf dem funktionierenden Stand mit direkter SVG-zu-PNG-Konvertierung beim Avatar-Upload.

Geändert wurde ausschließlich der Export des Preview-Bildes:
- Das Preview-Bild wird im Export nicht mehr verändert, ersetzt oder neu dimensioniert.
- `html2canvas` übernimmt exakt das Bild-Element aus der Live-Vorschau.
- Dadurch bleiben Größe, Ausschnitt, Rundung und Position identisch zur Vorschau.
- Die Exportauflösung wurde auf 3x erhöht, ohne die CSS-Geometrie zu verändern.

Die funktionierende SVG-zu-PNG-Konvertierung des Avatars bleibt unverändert erhalten.
