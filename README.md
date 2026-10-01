# trustedDialog Preview Builder - Round Avatar Export Fix

Diese Version basiert auf der bereitgestellten `app.py` und ändert ausschließlich die Avatar-Behandlung beim PNG-Export.

- Live-Vorschau bleibt unverändert.
- Der bestehende iPhone-Frame bleibt unverändert.
- Das Avatar-Logo bleibt beim Export 38 × 38 px und kreisrund.
- Das Avatar-Bild wird beim Export nicht mehr in ein CSS-Hintergrundbild umgewandelt, wodurch die runde Darstellung verloren bzw. abgeschnitten werden konnte.
