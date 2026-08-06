# Vor dem Veröffentlichen

Abzuarbeiten vor jedem Push, der nach außen geht.

## Automatisch

```bash
python -m pytest
python tools/freigeben.py --pruefen
```

Beide müssen sauber durchlaufen. `test_auslieferung.py` deckt die meisten
Punkte unten bereits ab — die Liste steht trotzdem hier, weil ein Test nur
prüft, woran jemand vorher gedacht hat.

## Keine Unternehmensdaten im Repository

- [ ] `git ls-files` enthält keine `*.sqlite`
- [ ] `git ls-files` enthält nichts aus `exporte/`
- [ ] Keine echten Firmen-, Personen- oder Systemnamen in Beispieldaten
- [ ] `.zeit/laufend.json` ist ignoriert, `.zeit/sessions.jsonl` ist versioniert

## Keine externen Ressourcen

- [ ] Entwicklertools, Reiter Netzwerk, Cache deaktiviert, Seite neu laden
- [ ] Es erscheint ausschließlich `127.0.0.1` — keine einzige Fremdanfrage
- [ ] Dasselbe für `exporte/dossier.html`, direkt im Browser geöffnet

Das ist kein Detail, sondern das Versprechen des Werkzeugs. Eine einzige
Schriftreferenz auf einen CDN würde es widerlegen.

## Regelwerk

- [ ] Verifikationsstand und Versionsnummer widersprechen sich nicht
- [ ] `VERIFIKATION.md` ist auf dem aktuellen Stand
- [ ] Änderungshistorie führt den letzten Stand mit Datum und Prüfer
- [ ] `lesarten.omnibus`: `eingearbeitet`, `geprueft` und die offene
      Checkliste im `hinweis` geben den wahren Stand wieder; kein Befehl steht
      zugleich als offen und als abgebildet
- [ ] Solange `eingearbeitet` false ist, trägt die README den Omnibus-Vorbehalt

Den Vorbehalt im Dossier prüft die Suite, nicht diese Liste: Der Haken hing
zuvor an einer Aussage über den Code, die niemand nachrechnen konnte, und war
falsch gesetzt, weil das Dossier den Vorbehalt gar nicht kannte. Er hängt jetzt
an `lesarten.omnibus.eingearbeitet`, und die Tests in `test_export.py`
(`test_dossier_in_lesart_omnibus_traegt_den_vorbehalt` samt Gegenprobe)
verlangen ihn. Für die README gibt es keinen solchen Test, deshalb bleibt sie
als Haken stehen.

## Schriften

- [ ] Jede in der CSS deklarierte Schrift hat eine `@font-face`-Regel
- [ ] Jede referenzierte `.woff2` liegt unter `app/static/schriften/`
- [ ] Zu jeder Schrift liegt ihre OFL-Lizenz daneben

## Git

- [ ] `git log --format="%an <%ae>" -5` zeigt die Noreply-Adresse,
      keine private Mail
- [ ] Commit-Nachrichten beschreiben, was sich fachlich geändert hat

## Zeiterfassung

- [ ] `python tools/zeit.py status` — keine vergessene Sitzung offen
- [ ] Keine unplausibel langen Sitzungen in `.zeit/sessions.jsonl`

Eine geschönte oder versehentlich durchlaufende Bilanz ist wertlos für den
Zweck, für den sie geführt wird.
