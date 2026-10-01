# trustedDialog Preview Builder - Avatar Export v2

Nur der Export des hochgeladenen Avatars wurde geändert:
- SVG bleibt in der Live-Vorschau unverändert.
- Für den PNG-Export wird das SVG serverseitig als PNG gerastert.
- Im Export wird das Avatarbild explizit auf 38 x 38 px gesetzt und mit `border-radius: 50%` plus `clip-path: circle(...)` rund beschnitten.
- Das Avatarbild wird nicht mehr in ein CSS-Hintergrundbild umgewandelt.

Der iPhone-Frame und der restliche Stand der bereitgestellten app.py bleiben unverändert.
