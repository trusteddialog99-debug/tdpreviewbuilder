# trustedDialog Preview Builder - SVG sofort zu PNG

Nur die Avatar-Pipeline wurde geändert:
- SVG kann weiterhin im Upload gewählt werden.
- Direkt nach dem Laden der Vorschau wird ein hochgeladenes SVG im Browser auf Canvas gerendert und in ein PNG umgewandelt.
- Danach verwendet die Vorschau dieses PNG weiter.
- Der spätere GMX-PNG-Export verwendet damit ebenfalls nur noch das bereits konvertierte PNG.
- Keine CairoSVG-/libcairo-Abhängigkeit.

Alle übrigen Layout- und Exportfunktionen bleiben unverändert.
