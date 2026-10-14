# trustedDialog Preview Builder - Sender & Avatar Update

Dieses Paket enthält die vorhandenen Deployment-Dateien plus einen gezielten Updater für die aktuelle `app.py`.

## Anwendung

1. Lege deine aktuelle `app.py` in dasselbe Verzeichnis wie `app_patch.py`.
2. Führe einmal aus:

```bash
python app_patch.py
```

Der Updater:
- erstellt automatisch `app.before_sender_avatar_fix.py` als Backup,
- verbessert die Markennamen-Erkennung,
- punktet zu lange Absender in der Inbox aus,
- setzt die Fallback-Avatarfarbe auf `#B8DDFD` mit blauer Schrift,
- setzt für das Logo der ersten trustedDialog-Mail einen weißen Avatar-Hintergrund,
- verändert Header, Footer, Preview-Bild-Logik und Export nicht,
- prüft die resultierende `app.py` auf Python-Syntax.

## Deployment-Dateien

- `requirements.txt`
- `packages.txt`

`README_source.md` ist die mitgelieferte README der Vorgängerversion.
