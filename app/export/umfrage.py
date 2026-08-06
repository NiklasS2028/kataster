"""
export/umfrage.py - Fragebogen zur Erhebung nicht erfasster KI-Nutzung.

Der Fragebogen ist bewusst anonym und bewusst kurz. Wer befuerchtet, dass eine
ehrliche Antwort Aerger bringt, antwortet nicht - dann steht am Ende ein
Verzeichnis, das ordentlich aussieht und nichts wert ist. Die Einleitung sagt
das ausdruecklich zu, und der Bogen fragt keinen Namen ab.

Ohne den Vorbehalt aus app/hinweise.py, und das ist Absicht: Der Bogen ist ein
Erhebungsmittel, kein Nachweis. Er trifft keine Einstufung, nennt keine Norm
und wird niemandem vorgelegt, der daraus eine Rechtsfolge ableiten koennte. Ein
Hinweis, dass dies keine Rechtsberatung sei, waere an einer Frage nach dem
benutzten Werkzeug ohne Gegenstand - und er wuerde die Zusage der
Folgenlosigkeit verwaessern, die den Bogen ueberhaupt beantwortbar macht. Die
vier Nachweise unter export/ tragen den Vorbehalt ausnahmslos.
"""

from __future__ import annotations

from datetime import datetime
from html import escape

STIL = """
@page { size: A4; margin: 18mm; }
body { font-family: Georgia, "Times New Roman", serif; font-size: 11pt;
       line-height: 1.55; color: #1B1D1A; max-width: 175mm; margin: 0 auto; padding: 20px; }
h1 { font-size: 16pt; margin: 0 0 4px; }
h2 { font-size: 11.5pt; margin: 22px 0 6px; }
.zusage { border: 1.5px solid #1B1D1A; padding: 12px 14px; margin: 16px 0 20px; }
.zusage strong { display: block; margin-bottom: 4px; }
table { width: 100%; border-collapse: collapse; margin: 10px 0 6px; }
th { text-align: left; font-size: 8pt; letter-spacing: 0.08em; text-transform: uppercase;
     color: #5A5E57; border-bottom: 1.2px solid #1B1D1A; padding: 4px 6px 4px 0; }
td { border-bottom: 0.5px solid #CFC7B4; padding: 13px 6px; }
.beispiele { color: #5A5E57; font-size: 10pt; }
.fuss { margin-top: 24px; padding-top: 8px; border-top: 0.5px solid #CFC7B4;
        font-size: 9pt; color: #5A5E57; }
"""


def fragebogen_html(organisation, zeitpunkt: datetime, zeilen: int = 6) -> str:
    firma = organisation.get("name") or "[Name des Unternehmens]"
    ansprech = organisation.get("ansprechpartner") or "[Ansprechperson eintragen]"

    h = []
    h.append("<!doctype html><html lang='de'><head><meta charset='utf-8'>")
    h.append(f"<title>Umfrage KI-Nutzung &middot; {escape(firma)}</title>")
    h.append(f"<style>{STIL}</style></head><body>")
    h.append("<h1>Welche KI-Werkzeuge nutzen Sie bei der Arbeit?</h1>")
    h.append(f"<p>{escape(firma)} &middot; anonyme Erhebung</p>")

    h.append("<div class='zusage'>")
    h.append("<strong>Diese Umfrage ist anonym und folgenlos.</strong>")
    h.append("Wir fragen nicht nach Ihrem Namen und werten nichts personenbezogen "
             "aus. Es geht nicht darum, jemandem etwas nachzuweisen, sondern darum, "
             "zu wissen, was im Haus tatsächlich genutzt wird. Wer ein Werkzeug "
             "nennt, das bisher nicht freigegeben war, muss mit keiner Folge rechnen "
             "&mdash; im Gegenteil: Nur was bekannt ist, lässt sich absichern.")
    h.append("</div>")

    h.append("<h2>Was zählt dazu?</h2>")
    h.append("<p class='beispiele'>Alles, was Texte, Bilder, Code oder Auswertungen "
             "erzeugt oder Entscheidungen vorschlägt. Zum Beispiel ChatGPT, Copilot, "
             "Gemini, Claude, DeepL, Midjourney, Übersetzungs- und "
             "Zusammenfassungsfunktionen in Programmen, die Sie ohnehin verwenden. "
             "Auch private Zugänge, die Sie für die Arbeit nutzen, und kostenlose "
             "Versionen.</p>")

    h.append("<h2>Ihre Angaben</h2>")
    h.append("<table><thead><tr>")
    h.append("<th style='width:32%'>Werkzeug</th>")
    h.append("<th style='width:38%'>Wofür nutzen Sie es?</th>")
    h.append("<th style='width:15%'>Wie oft?</th>")
    h.append("<th style='width:15%'>Bereich</th>")
    h.append("</tr></thead><tbody>")
    for _ in range(zeilen):
        h.append("<tr><td></td><td></td><td></td><td></td></tr>")
    h.append("</tbody></table>")
    h.append("<p class='beispiele'>Bei &bdquo;Wie oft&ldquo;: t&auml;glich, "
             "w&ouml;chentlich, selten. "
             "Der Bereich ist freiwillig und dient nur der Zuordnung von Schulungen.</p>")

    h.append("<h2>Noch eine Frage</h2>")
    h.append("<p>Gibt es eine Aufgabe, bei der Sie sich ein KI-Werkzeug wünschen "
             "würden, aber keines haben?</p>")
    h.append("<table><tbody><tr><td style='height:26mm'></td></tr></tbody></table>")

    h.append(f"<div class='fuss'>Bitte zurück an: {escape(ansprech)} &middot; "
             f"Stand {zeitpunkt:%d.%m.%Y}. "
             "Ausgefüllte Bögen werden nach der Auswertung vernichtet.</div>")
    h.append("</body></html>")
    return "\n".join(h)


def vorlage_csv() -> str:
    """Vorlage fuer die Rueckmeldung per Tabelle, etwa aus einem Formulardienst."""
    return (
        "Werkzeug;Wofuer;Wie oft;Bereich\n"
        "ChatGPT;Texte formulieren;taeglich;Vertrieb\n"
        "DeepL;Uebersetzungen;woechentlich;Einkauf\n"
    )
