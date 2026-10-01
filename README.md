# trustedDialog Preview Builder - Preview Export Exact Crop

Nur die Preview-Grafik beim PNG-Export wurde geändert:
- Vor dem Export wird das hochgeladene Preview-Bild im Browser mit derselben `cover`-Logik wie die Live-Vorschau zugeschnitten.
- Daraus wird ein hochauflösendes PNG mit 1012 × 384 px erzeugt, exakt 4x der sichtbaren 253 × 96 px Fläche.
- Dieses bereits korrekt zugeschnittene PNG wird anschließend ohne weitere Skalierungslogik in den Export eingesetzt.
- Dadurch bleibt der Bildausschnitt wie in der Vorschau und wird nicht verzogen.

Die funktionierende Avatar-Verarbeitung bleibt unverändert.
