# trustedDialog Preview Builder - Avatar + iPhone Frame Fix

Es wurden ausschließlich diese beiden Punkte angepasst:

1. **Avatar-Logo**
   - bleibt rund maskiert,
   - wird mit `contain` statt `cover` dargestellt,
   - wird dadurch weder in der Vorschau noch beim PNG-Export abgeschnitten.

2. **iPhone-Frame**
   - dunkler/schwarzer Grundrahmen,
   - metallisch graue Außen- und Innenkanten,
   - zusätzliche seitliche Hardware-Konturen,
   - dieselbe Frame-Darstellung wird auch beim PNG-Export erzwungen.

Alle übrigen Funktionen und Layoutwerte bleiben unverändert.
