# Sicherheit

Kataster verarbeitet Angaben darüber, welche KI-Systeme ein Unternehmen
einsetzt, wofür, mit welchen Kosten und mit welcher rechtlichen Einstufung. Das
sind Daten, die ein Unternehmen normalerweise nicht aus der Hand gibt. Die
Bauweise ist darauf ausgelegt, dass sie das auch nicht müssen.

## Wo die Daten liegen

Alles bleibt auf dem Rechner, auf dem das Werkzeug läuft.

- Der Server bindet ausschließlich an `127.0.0.1` (Port 8771). Er ist im Netz
  nicht erreichbar, auch nicht im lokalen.
- Die Datenbank ist eine SQLite-Datei im Projektordner (`kataster.sqlite`).
- Die Nachweise entstehen als Dateien unter `exporte/`.
- Beides ist in `.gitignore` eingetragen und wird nicht versioniert.

## Kein Cloud-Dienst, keine Telemetrie

- Es gibt kein Konto, keine Registrierung, keinen Server, zu dem eine
  Verbindung aufgebaut wird.
- Es gibt keine Nutzungsstatistik, keine Absturzberichte, keine Prüfung auf
  Aktualisierungen.
- Beim Seitenaufbau geht keine einzige Anfrage an einen fremden Host. Die
  Schriften liegen als `.woff2` im Projekt, die Stile stehen inline.
- Das Nachweis-Dossier ist eine eigenständige HTML-Datei ohne externe Verweise.
  Es lässt sich in fünf Jahren aus einem Archiv holen und ist dann noch
  vollständig.
- Es findet keine automatisierte Auslegung statt. Die Einstufung ist
  regelbasiert und deterministisch, es wird kein Modell aufgerufen, und damit
  verlässt auch auf diesem Weg nichts den Rechner.

Das ist nicht nur Absicht, sondern geprüft: `tests/test_auslieferung.py`
verweigert den grünen Lauf, sobald eine Vorlage oder die CSS auf eine fremde
Adresse zeigt oder eine deklarierte Schrift nicht lokal eingebunden ist. Eine
einzige Schriftreferenz auf ein CDN würde das Versprechen widerlegen, deshalb
ist die Prüfung inhaltlich und nicht kosmetisch.

Die Abhängigkeiten sind aus demselben Grund knapp gehalten: Flask und PyYAML,
für die Tests pytest. Mehr steht nicht in `requirements.txt`.

## Was das Werkzeug nicht leistet

Ehrlich benannt, damit niemand es für etwas hält, was es nicht ist:

- **Keine Zugangskontrolle.** Es gibt keine Anmeldung und keine Rollen. Wer
  Zugriff auf den Rechner und den Projektordner hat, sieht den Bestand und kann
  ihn ändern. Der Schutz ist der Rechner, nicht die Anwendung.
- **Keine Verschlüsselung im Ruhezustand.** Die SQLite-Datei liegt im Klartext.
  Wer sie schützen will, verschlüsselt das Dateisystem.
- **`start.py` startet mit `debug=True`.** Der Debugger von Werkzeug erlaubt im
  Fehlerfall das Ausführen von Code über die Weboberfläche. Weil der Server nur
  auf `127.0.0.1` hört, ist das kein Netzwerkrisiko, wohl aber eines auf einem
  Rechner, den sich mehrere Personen teilen. Wer in einer solchen Umgebung
  arbeitet, startet die Anwendung ohne Debug-Modus.
- **Keine Sicherung.** Es gibt keine automatische Sicherungskopie der
  Datenbank. Die Verantwortung dafür liegt beim Betrieb.

## Eine Schwachstelle melden

Bitte nicht über einen öffentlichen Issue, sondern über die private Meldung von
Sicherheitslücken auf GitHub („Report a vulnerability" im Reiter Security des
Repositorys <https://github.com/NiklasS2028/kataster>).

Hilfreich sind: Was passiert, was Sie erwartet hätten, und wie sich der Fall
nachstellen lässt. Das Projekt entsteht im Rahmen einer Bachelorarbeit und wird
in der Freizeit gepflegt; eine Antwortfrist kann ich nicht zusagen, eine
Antwort schon.

## Was ausdrücklich keine Schwachstelle ist

Die fehlende Zugangskontrolle und die unverschlüsselte Datenbank sind
Entwurfsentscheidungen für ein Werkzeug, das auf einem einzelnen Arbeitsplatz
läuft, und oben benannt. Wer Kataster auf einen erreichbaren Host stellt, ändert
die Voraussetzung, unter der diese Entscheidungen getroffen wurden. Dafür ist es
nicht gebaut.
