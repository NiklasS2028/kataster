"""
export/richtlinie.py - Entwurf einer KI-Richtlinie aus dem erfassten Bestand.

Bewusst als Markdown und bewusst als Entwurf: Eine Richtlinie, die niemand
gelesen und angepasst hat, ist wertlos. Das Dokument enthaelt deshalb sichtbare
Stellen, die auszufuellen sind, statt sie mit Platzhaltern zu kaschieren.
"""

from __future__ import annotations

from datetime import datetime

from ..hinweise import als_markdown


def _liste(systeme, bedingung):
    treffer = [s for s in systeme if bedingung(s)]
    if not treffer:
        return "_Derzeit keine._\n"
    zeilen = []
    for s in treffer:
        zusatz = f" ({s['zweck']})" if s.get("zweck") else ""
        zeilen.append(f"- **{s['name']}**{zusatz}")
    return "\n".join(zeilen) + "\n"


def richtlinie_text(organisation, systeme, regelwerk, klassennamen, zeitpunkt: datetime) -> str:
    name = organisation.get("name") or "[Name des Unternehmens]"
    ansprech = organisation.get("ansprechpartner") or "[Name eintragen]"

    def klasse(s):
        e = s.get("einstufung")
        return e["klasse"] if e else None

    t = []
    t.append(f"# Richtlinie zum Einsatz von KI-Systemen\n")
    t.append(f"**{name}**\n")
    t.append(f"Entwurfsstand: {zeitpunkt:%d.%m.%Y}  ")
    t.append(f"Grundlage: Regelwerk {regelwerk.version}, Rechtsstand {regelwerk.rechtsstand}\n")
    t.append("> Dieser Entwurf wurde aus dem erfassten Bestand erzeugt. Er ist vor")
    t.append("> Inkraftsetzung zu prüfen, an Ihre Abläufe anzupassen und von der")
    t.append("> Geschäftsleitung freizugeben. Er ist keine Rechtsberatung.\n")

    t.append("## 1. Zweck und Geltungsbereich\n")
    t.append("Diese Richtlinie regelt, welche KI-Systeme im Unternehmen eingesetzt")
    t.append("werden dürfen, wofür sie genutzt werden und welche Daten dabei")
    t.append("verarbeitet werden dürfen. Sie gilt für alle Beschäftigten sowie für")
    t.append("Personen, die in unserem Auftrag tätig sind.\n")

    t.append("## 2. Freigegebene Systeme\n")
    t.append("Nur die folgenden Systeme dürfen dienstlich genutzt werden:\n")
    t.append(_liste(systeme, lambda s: s["status"] == "freigegeben"))

    geduldet = [s for s in systeme if s["status"] == "geduldet"]
    if geduldet:
        t.append("\n### Geduldet, aber nicht freigegeben\n")
        t.append("Diese Systeme sind bekannt und werden derzeit geprüft. Bis zu einer")
        t.append("Entscheidung ist die Eingabe personenbezogener Daten und")
        t.append("vertraulicher Inhalte untersagt.\n")
        t.append(_liste(systeme, lambda s: s["status"] == "geduldet"))

    untersagt = [s for s in systeme if s["status"] == "untersagt"]
    if untersagt:
        t.append("\n### Untersagt\n")
        t.append(_liste(systeme, lambda s: s["status"] == "untersagt"))

    t.append("\n## 3. Umgang mit Daten\n")
    t.append("In Eingaben an KI-Systeme dürfen **nicht** eingegeben werden:\n")
    t.append("- personenbezogene Daten von Beschäftigten, Kunden oder Bewerbern,")
    t.append("  soweit das System dafür nicht ausdrücklich freigegeben ist")
    t.append("- Geschäftsgeheimnisse, Kalkulationen, Verträge, Quellcode")
    t.append("- Zugangsdaten und Schlüssel jeder Art\n")
    ohne_av = [s for s in systeme if s["status"] == "freigegeben" and not s.get("av_vertrag")]
    if ohne_av:
        t.append("Für folgende freigegebene Systeme liegt **kein**")
        t.append("Auftragsverarbeitungsvertrag vor. Bei ihnen gilt die Einschränkung")
        t.append("ohne Ausnahme:\n")
        t.append(_liste(systeme, lambda s: s in ohne_av))

    t.append("\n## 4. Prüfpflicht der Ergebnisse\n")
    t.append("KI-Systeme erzeugen plausibel klingende, aber falsche Ergebnisse. Jede")
    t.append("Ausgabe ist vor Verwendung fachlich zu prüfen. Die Verantwortung für")
    t.append("das Arbeitsergebnis bleibt bei der Person, die es verwendet.\n")

    hochrisiko = [s for s in systeme if klasse(s) == "hochrisiko"]
    if hochrisiko:
        t.append("\n## 5. Systeme mit erhöhten Anforderungen\n")
        t.append("Für die folgenden Systeme gelten zusätzliche Pflichten. Sie dürfen")
        t.append("nur von eingewiesenen Personen und nur entsprechend der")
        t.append("Betriebsanleitung des Anbieters verwendet werden. Ergebnisse dürfen")
        t.append("nicht ungeprüft Grundlage von Entscheidungen über Personen sein.\n")
        for s in hochrisiko:
            e = s["einstufung"]
            regeln = ", ".join(e["ausgeloest_durch"]) or "—"
            t.append(f"- **{s['name']}** — ausgelöst durch {regeln}")
            if e.get("bestandsschutz_greift"):
                t.append("  (derzeit Bestandsschutz nach Art. 111 Abs. 2 KI-VO)")
        t.append("")

    verboten = [s for s in systeme if klasse(s) == "verboten"]
    if verboten:
        t.append("\n## 6. Untersagte Praktiken\n")
        t.append("Die folgenden Systeme wurden als verbotene Praktik eingestuft. Ihr")
        t.append("Einsatz ist mit sofortiger Wirkung einzustellen:\n")
        for s in verboten:
            t.append(f"- **{s['name']}** — {', '.join(s['einstufung']['ausgeloest_durch'])}")
        t.append("")

    t.append("\n## Kennzeichnung nach außen\n")
    transparenz = [s for s in systeme if klasse(s) == "transparenz"]
    if transparenz:
        t.append("Bei folgenden Systemen sind Kennzeichnungs- oder")
        t.append("Informationspflichten zu beachten:\n")
        t.append(_liste(systeme, lambda s: klasse(s) == "transparenz"))
    else:
        t.append("Derzeit sind keine besonderen Kennzeichnungspflichten erfasst.\n")

    t.append("\n## Meldewege\n")
    t.append("Auffällige, diskriminierende oder erkennbar falsche Ergebnisse sowie")
    t.append("jeder Verdacht auf einen Datenabfluss sind unverzüglich zu melden an:\n")
    t.append(f"**{ansprech}**\n")
    t.append("Wer ein KI-System einsetzen möchte, das hier nicht aufgeführt ist,")
    t.append("meldet dies vorab. Eigenmächtige Einführung ist nicht gestattet — nicht")
    t.append("um Initiative zu bremsen, sondern weil unbekannte Systeme sich weder")
    t.append("prüfen noch absichern lassen.\n")

    t.append("\n## Schulung\n")
    t.append("Alle Beschäftigten, die mit KI-Systemen arbeiten, erhalten eine auf")
    t.append("ihre Tätigkeit zugeschnittene Einweisung. Umfang und Teilnahme werden")
    t.append("dokumentiert. Die Einweisung wird bei wesentlichen Änderungen")
    t.append("wiederholt, mindestens jedoch jährlich.\n")

    t.append("\n## Inkraftsetzung\n")
    t.append("Diese Richtlinie tritt in Kraft am: __________________\n")
    t.append("Freigegeben durch: __________________________________\n")
    t.append("\n---\n")
    t.append(f"_Entwurf erzeugt mit Kataster am {zeitpunkt:%d.%m.%Y um %H:%M} Uhr._  ")
    t.append(f"_Regelwerk {regelwerk.version}, Rechtsstand {regelwerk.rechtsstand}._  ")
    t.append(als_markdown())
    return "\n".join(t) + "\n"
