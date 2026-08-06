"""
hinweise.py - Der Vorbehalt, den jede Ausgabe traegt.

Der Hinweis stand vorher an sechs Stellen in fuenf Fassungen: einmal ohne
"bescheinigt keine Konformitaet", zweimal als blosses "Keine Rechtsberatung",
einmal gar nicht (inventar.csv). Vier Texte an vier Orten driften auseinander,
und beim Vorbehalt ist die Drift keine Schoenheitsfrage: Er ist die Aussage
darueber, was das Werkzeug NICHT leistet.

Warum nicht meta.hinweis im Regelwerk, obwohl der ohnehin geladen wird:

  1. Der SHA-256 laeuft ueber die gesamte Regelwerksdatei und steht als
     Pruefsumme in jedem Dossier. Kaeme der angezeigte Text von dort, wuerde
     jede Umformulierung am Produkttext die Pruefsumme aller kuenftigen
     Nachweise aendern und eine neue regelwerk_version verlangen. Produkttext
     bekaeme das Gewicht von Rechtsinhalt.
  2. Die YAML ist durchgaengig ASCII-transliteriert, weil sie eigenstaendig
     weitergegeben wird. Als Textquelle fuer Oberflaeche und Markdown truege
     sie "Selbsteinschaetzung" in die Anzeige.

Die Regelwerksdatei behaelt ihren eigenen Hinweis in meta.hinweis: Sie wandert
unter CC BY einzeln weiter und muss ihn selbst mitfuehren. Dass beide dasselbe
sagen, sichert ein Test (test_auslieferung.py), nicht eine gemeinsame Variable.
"""

from __future__ import annotations

TITEL = "Kein Rechtsrat."

TEXT = (
    "Kataster ist ein Werkzeug zur strukturierten Selbsteinschätzung und "
    "Dokumentation. Es trifft keine rechtliche Bewertung, bescheinigt keine "
    "Konformität und ersetzt keine Beratung. Verbindlich sind allein die im "
    "Amtsblatt der Europäischen Union veröffentlichten Texte (Art. 297 AEUV)."
)

# Woran der Test den Hinweis erkennt. Bewusst schmal: die Fundstelle, die die
# Aussage traegt, und ein Marker fuer die Absage selbst. Alles darueber hinaus
# wuerde bei jeder Umformulierung brechen, ohne dass etwas kaputt waere.
KERNSTELLE = "Art. 297 AEUV"
MARKER = ("kein rechtsrat", "keine rechtsberatung")


def als_text() -> str:
    """Fliesstext ohne Auszeichnung."""
    return f"{TITEL} {TEXT}"


def als_html() -> str:
    """Fuer das Dossier und die Fusszeile der Oberflaeche."""
    return f"<strong>{TITEL}</strong> {TEXT}"


def als_markdown() -> str:
    """Fuer Richtlinie und Schulungsmatrix."""
    return f"**{TITEL}** {TEXT}"


def als_csv_zeilen() -> list[list[str]]:
    """Fuer inventar.csv.

    Eine Kommentarsyntax kennt CSV nicht: Ein fuehrendes '#' waere fuer
    Tabellenkalkulationen eine gewoehnliche Datenzeile, und eine Zeile VOR der
    Kopfzeile wuerde die Spaltenerkennung zerstoeren. Der Hinweis steht deshalb
    als letzte Zeile in der ersten Spalte, abgesetzt durch eine Leerzeile. Die
    Kopfzeile bleibt Zeile 1, jede Datenzeile bleibt vollstaendig, und wer die
    Datei nach Spalten filtert, bekommt den Hinweis als einzelnes Feld statt als
    zerschossenen Datensatz.
    """
    return [[], [als_text()]]
