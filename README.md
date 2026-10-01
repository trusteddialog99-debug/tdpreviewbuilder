# trustedDialog Preview Builder - PNG Download Fix

Die PNG-Downloadfunktion wurde technisch umgestellt:
- Browser-Rendering jetzt mit `html2canvas` statt SVG `foreignObject`.
- Exportiert wird weiterhin ausschließlich die GMX-Smartphone-Vorschau.
- Exportauflösung: 2x.
- Dateiname: `GMX_trustedDialogPreview_[Absender].png`.
- Der Absender stammt weiterhin aus dem Feld **Absender / Marke**.

Die bestehende Vorschau und deren Inhalte wurden nicht verändert.
