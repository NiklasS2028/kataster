# Bilder fuer die README

Zwei Aufnahmen, die im README verlinkt sind:

| Datei | Ansicht |
|---|---|
| `verzeichnis.png` | Bestandsverzeichnis mit dem Musterbestand — alle vier Schraffuren nebeneinander, Pflichtenhinweis oben |
| `bestandsblatt.png` | Detailseite des Bewerbermanagements — Hochrisiko-Einstufung, Bestandsschutz-Hinweis und dokumentierte Ausnahme untereinander |

So entstehen sie:

```bash
python beispiel.py --neu
python start.py
```

Dann im Browser `http://127.0.0.1:8771` aufrufen, Fenster auf etwa 1280 Pixel
Breite ziehen und die ganze Seite aufnehmen. Unter Firefox geht das ohne
Zusatzwerkzeug: Rechtsklick, "Bildschirmfoto aufnehmen", "Gesamte Seite
speichern".

Vor dem Aufnehmen pruefen, dass im Kartenkopf `25/25 verifiziert` steht — mit
Entwurfshinweis in der Fusszeile sieht das Werkzeug unfertig aus.
