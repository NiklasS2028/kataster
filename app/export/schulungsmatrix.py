"""
export/schulungsmatrix.py - Wer braucht welche Schulungsinhalte.

Art. 4 KI-VO i. d. F. der VO (EU) 2026/1744 verlangt Massnahmen, die
technische Kenntnisse, Erfahrung, Aus- und Fortbildung, Einsatzkontext und die
betroffenen Personengruppen beruecksichtigen, ohne fuer irgendeine Person ein
bestimmtes Kompetenzniveau zu garantieren (Abs. 1 Satz 2). Die Matrix leitet
die Inhalte aus dem ab, was im Unternehmen tatsaechlich eingesetzt wird, und
dokumentiert die ergriffenen Massnahmen.
"""

from __future__ import annotations

from datetime import datetime

# Bereichsbezeichnung im Inventar -> Zielgruppe im Regelwerk
ZIELGRUPPEN = {
    "personal": ["personal", "hr", "human resources"],
    "marketing": ["marketing", "kommunikation", "pr"],
    "vertrieb": ["vertrieb", "sales"],
    "fuehrung": ["geschäftsführung", "geschaeftsfuehrung", "leitung", "vorstand"],
    "it": ["it", "edv", "technik"],
    "compliance": ["compliance", "recht", "datenschutz"],
}


def _zielgruppe(abteilung: str | None) -> str:
    if not abteilung:
        return "alle"
    klein = abteilung.strip().lower()
    for gruppe, begriffe in ZIELGRUPPEN.items():
        if any(b in klein for b in begriffe):
            return gruppe
    return "alle"


def matrix_text(organisation, systeme, regelwerk, zeitpunkt: datetime) -> str:
    name = organisation.get("name") or "[Name des Unternehmens]"
    bausteine = regelwerk.schulungsbausteine

    hat_hochrisiko = any(
        (s.get("einstufung") or {}).get("klasse") == "hochrisiko" for s in systeme
    )

    # Welche Bereiche kommen im Bestand ueberhaupt vor?
    bereiche: dict[str, list[str]] = {}
    for s in systeme:
        gruppe = _zielgruppe(s.get("abteilung"))
        bereiche.setdefault(gruppe, []).append(s["name"])

    t = []
    t.append("# Schulungsmatrix KI-Kompetenz\n")
    t.append(f"**{name}**\n")
    t.append(f"Stand: {zeitpunkt:%d.%m.%Y}  ")
    t.append(f"Grundlage: Art. 4 KI-VO i. d. F. der VO (EU) 2026/1744, "
             f"Regelwerk {regelwerk.version}\n")
    t.append("> Art. 4 verlangt Maßnahmen, die Vorkenntnisse, Aus- und Fortbildung,")
    t.append("> Einsatzkontext und die betroffenen Personengruppen berücksichtigen.")
    t.append("> Ein bestimmtes Niveau an KI-Kompetenz muss nach Art. 4 Abs. 1 Satz 2")
    t.append("> für keine Person garantiert werden. Diese Matrix leitet die Inhalte")
    t.append("> aus den tatsächlich erfassten Systemen ab und dokumentiert die")
    t.append("> ergriffenen Maßnahmen, nicht ein erreichtes Kompetenzniveau.\n")

    t.append("## Bausteine\n")
    t.append("| Nr. | Inhalt | Für wen |")
    t.append("|---|---|---|")
    for b in bausteine:
        zielgruppen = b.get("zielgruppen", ["alle"])
        if "alle_mit_hochrisikosystem" in zielgruppen and not hat_hochrisiko:
            continue
        wer = "Alle Beschäftigten" if "alle" in zielgruppen else ", ".join(
            z.replace("_", " ").capitalize() for z in zielgruppen
        )
        if "alle_mit_hochrisikosystem" in zielgruppen:
            wer = "Alle, die ein Hochrisiko-System bedienen"
        fundstelle = f" ({b['fundstelle']})" if b.get("fundstelle") else ""
        t.append(f"| {b['id']} | {b['baustein']}{fundstelle} | {wer} |")
    t.append("")

    t.append("## Zuordnung nach Bereich\n")
    if not bereiche:
        t.append("_Noch keine Systeme erfasst._\n")
    else:
        for gruppe, namen in sorted(bereiche.items()):
            bezeichnung = "Alle Bereiche" if gruppe == "alle" else gruppe.capitalize()
            t.append(f"### {bezeichnung}\n")
            t.append("Eingesetzte Systeme: " + ", ".join(sorted(set(namen))) + "\n")
            passende = [
                b for b in bausteine
                if "alle" in b.get("zielgruppen", [])
                or gruppe in b.get("zielgruppen", [])
                or ("alle_mit_hochrisikosystem" in b.get("zielgruppen", []) and hat_hochrisiko)
            ]
            for b in passende:
                t.append(f"- {b['id']} — {b['baustein']}")
            t.append("")

    t.append("## Ergriffene Maßnahmen\n")
    t.append("Art. 4 verlangt ergriffene Maßnahmen, kein garantiertes Niveau. Für")
    t.append("jede Maßnahme ist festzuhalten, worauf sie zugeschnitten war, damit die")
    t.append("Berücksichtigung von Vorkenntnissen und Einsatzkontext nach Art. 4")
    t.append("Abs. 1 belegt ist. Ohne diese Angaben lässt sich die Durchführung")
    t.append("später nicht nachweisen.\n")
    t.append("| Maßnahme | Datum | Teilnehmerkreis | Zuschnitt (Vorkenntnisse, Einsatzkontext) | Nachweis |")
    t.append("|---|---|---|---|---|")
    t.append("|  |  |  |  |  |")
    t.append("|  |  |  |  |  |")
    t.append("|  |  |  |  |  |\n")

    t.append("## Wiederholung\n")
    t.append("Die Einweisung ist zu wiederholen, wenn ein neues System eingeführt")
    t.append("wird, wenn sich der Einsatzzweck eines Systems wesentlich ändert oder")
    t.append("wenn sich die Rechtslage ändert — mindestens jedoch jährlich.\n")

    t.append("---\n")
    t.append(f"_Erzeugt mit Kataster am {zeitpunkt:%d.%m.%Y um %H:%M} Uhr._  ")
    t.append("_Keine Rechtsberatung._")
    return "\n".join(t) + "\n"
