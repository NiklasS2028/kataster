#!/usr/bin/env python3
"""
verifizieren.py - Verwaltet den Verifikationsstand des Regelwerks.

Der Abgleich gegen den amtlichen Text ist Handarbeit und muss es bleiben.
Dieses Werkzeug nimmt nur das Drumherum ab: Es erzeugt eine nach Fundstelle
sortierte Arbeitsliste, damit jede Stelle im Normtext nur einmal aufgeschlagen
werden muss, und es setzt die Flags anschliessend, ohne dass 24-mal von Hand
in der YAML editiert wird.

Bearbeitet wird die Datei zeilenweise als Text, nicht ueber einen YAML-Umlauf:
Die Kommentare im Regelwerk sind Teil seines Werts und wuerden beim
Serialisieren verloren gehen.

    python tools/verifizieren.py --stand
    python tools/verifizieren.py --arbeitsliste
    python tools/verifizieren.py V-01 V-02 V-03 --von "Niklas Steinhauser"
    python tools/verifizieren.py --zuruecksetzen V-01
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import date
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
REGELWERK = WURZEL / "rules" / "ai-act_2026-07-27.yaml"
ARBEITSLISTE = WURZEL / "VERIFIKATION.md"

EURLEX = "https://eur-lex.europa.eu/eli/reg/2024/1689/oj?locale=de"

ID_ZEILE = re.compile(r"^(\s*)-\s+id:\s*([A-Za-z]+-\d+)\s*$")
GEPRUEFT_ZEILE = re.compile(r"^(\s*)geprueft:\s*(true|false)\s*$")
ZUSATZ_ZEILE = re.compile(r"^\s*geprueft_(am|von):")


def _laden() -> list[str]:
    if not REGELWERK.exists():
        sys.exit(f"Regelwerk nicht gefunden: {REGELWERK}")
    return REGELWERK.read_text(encoding="utf-8").splitlines(keepends=True)


def _speichern(zeilen: list[str]) -> None:
    """Atomar schreiben - ein abgebrochener Lauf darf das Regelwerk nicht zerstoeren."""
    temp = REGELWERK.with_suffix(REGELWERK.suffix + ".tmp")
    temp.write_text("".join(zeilen), encoding="utf-8")
    temp.replace(REGELWERK)


def _bloecke(zeilen: list[str]) -> dict[str, tuple[int, int]]:
    """Ordnet jeder Regel-ID ihren Zeilenbereich zu."""
    grenzen: dict[str, tuple[int, int]] = {}
    offen: str | None = None
    einzug = 0

    for nummer, zeile in enumerate(zeilen):
        treffer = ID_ZEILE.match(zeile)
        if treffer:
            if offen:
                grenzen[offen] = (grenzen[offen][0], nummer)
            offen = treffer.group(2)
            einzug = len(treffer.group(1))
            grenzen[offen] = (nummer, len(zeilen))
            continue

        if offen and zeile.strip() and not zeile.startswith(" " * (einzug + 1)):
            # Ausrueckung: der Block ist zu Ende.
            grenzen[offen] = (grenzen[offen][0], nummer)
            offen = None

    return grenzen


def _stand(zeilen: list[str]) -> dict[str, bool]:
    stand: dict[str, bool] = {}
    for kennung, (start, ende) in _bloecke(zeilen).items():
        for zeile in zeilen[start:ende]:
            treffer = GEPRUEFT_ZEILE.match(zeile)
            if treffer:
                stand[kennung] = treffer.group(2) == "true"
                break
    return stand


def _setzen(kennungen: list[str], wert: bool, von: str | None) -> tuple[list[str], list[str]]:
    zeilen = _laden()
    grenzen = _bloecke(zeilen)
    heute = date.today().isoformat()

    geaendert, unbekannt = [], []
    for kennung in kennungen:
        if kennung not in grenzen:
            unbekannt.append(kennung)
            continue

        start, ende = grenzen[kennung]
        neu: list[str] = []
        gesetzt = False
        for zeile in zeilen[start:ende]:
            if ZUSATZ_ZEILE.match(zeile):
                continue  # alte Angaben verwerfen, gleich neu schreiben
            treffer = GEPRUEFT_ZEILE.match(zeile)
            if treffer and not gesetzt:
                einzug = treffer.group(1)
                neu.append(f"{einzug}geprueft: {'true' if wert else 'false'}\n")
                if wert:
                    neu.append(f"{einzug}geprueft_am: \"{heute}\"\n")
                    if von:
                        neu.append(f"{einzug}geprueft_von: \"{von}\"\n")
                gesetzt = True
                continue
            neu.append(zeile)

        if gesetzt:
            zeilen[start:ende] = neu
            grenzen = _bloecke(zeilen)   # Zeilennummern haben sich verschoben
            geaendert.append(kennung)

    if geaendert:
        _speichern(zeilen)
    return geaendert, unbekannt


def _regeldaten() -> list[dict]:
    import yaml
    daten = yaml.safe_load(REGELWERK.read_text(encoding="utf-8"))
    return daten.get("regeln", [])


def _gruppe(fundstelle: str) -> str:
    """Grobe Bucketbildung, damit man jede Normstelle nur einmal aufschlaegt."""
    if fundstelle.startswith("Anhang I "):
        return "Anhang I"
    if fundstelle.startswith("Anhang III"):
        return "Anhang III"
    treffer = re.match(r"(Art\. \d+)", fundstelle)
    return treffer.group(1) if treffer else fundstelle


def arbeitsliste_schreiben() -> None:
    regeln = _regeldaten()
    stand = _stand(_laden())

    gruppen: dict[str, list[dict]] = {}
    for regel in regeln:
        gruppen.setdefault(_gruppe(regel["fundstelle"]), []).append(regel)

    reihenfolge = sorted(
        gruppen,
        key=lambda g: (
            0 if g.startswith("Art. 5") else
            1 if g.startswith("Anhang I") and g != "Anhang III" else
            2 if g == "Anhang III" else
            3 if g.startswith("Art. 50") else 4,
            g,
        ),
    )

    t = []
    t.append("# Verifikation der Fundstellen\n")
    t.append(f"Amtlicher Text: <{EURLEX}>\n")
    t.append("Nach Fundstelle gruppiert: Jede Normstelle muss nur einmal")
    t.append("aufgeschlagen werden. Innerhalb einer Gruppe von oben nach unten")
    t.append("abarbeiten, dann die IDs sammeln und in einem Aufruf setzen.\n")
    t.append("**Zu pruefen ist jeweils:** Stimmt die Fundstelle? Deckt sich die")
    t.append("Frageformulierung mit dem Normtext? Fehlt eine Tatbestandsvariante?")
    t.append("Ist eine genannte Ausnahme vollstaendig wiedergegeben?\n")

    offen_gesamt = 0
    for gruppe in reihenfolge:
        eintraege = gruppen[gruppe]
        offen = [r for r in eintraege if not stand.get(r["id"])]
        offen_gesamt += len(offen)

        t.append(f"\n## {gruppe}")
        t.append(f"\n{len(eintraege)} Regeln, davon {len(offen)} offen\n")
        for regel in eintraege:
            haken = "x" if stand.get(regel["id"]) else " "
            frage = " ".join(regel["frage"].split())
            t.append(f"- [{haken}] **{regel['id']}** &middot; `{regel['fundstelle']}`  ")
            t.append(f"      {frage}  ")
            if regel.get("ausnahmen"):
                ausnahme = " ".join(regel["ausnahmen"].split())
                t.append(f"      _Ausnahme im Entwurf:_ {ausnahme}  ")
            if regel.get("hinweis"):
                hinweis = " ".join(regel["hinweis"].split())
                t.append(f"      _Hinweis:_ {hinweis}  ")

        ids = " ".join(r["id"] for r in offen)
        if ids:
            t.append(f"\n```\npython tools/verifizieren.py {ids} --von \"NAME\"\n```")

    t.append(f"\n---\n\nOffen: {offen_gesamt} von {len(regeln)}.")
    t.append("\nSolange nicht alle Regeln verifiziert sind, meldet")
    t.append("`Regelwerk.ausspielbar()` falsch, die Fusszeile weist auf den")
    t.append("Entwurfsstand hin, und das Nachweis-Dossier traegt einen Warnkasten.")

    ARBEITSLISTE.write_text("\n".join(t) + "\n", encoding="utf-8")
    print(f"Arbeitsliste geschrieben: {ARBEITSLISTE.name}")
    print(f"  {offen_gesamt} von {len(regeln)} Regeln offen")


def stand_zeigen() -> None:
    regeln = _regeldaten()
    stand = _stand(_laden())
    geprueft = [r["id"] for r in regeln if stand.get(r["id"])]
    offen = [r["id"] for r in regeln if not stand.get(r["id"])]

    print(f"Verifiziert: {len(geprueft)} von {len(regeln)}")
    if geprueft:
        print("  fertig: " + " ".join(geprueft))
    if offen:
        print("  offen:  " + " ".join(offen))
    else:
        print("  Regelwerk ist ausspielbar.")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verifikationsstand des Regelwerks verwalten")
    parser.add_argument("kennungen", nargs="*",
                        help="Regel-IDs, etwa V-01 H-03")
    parser.add_argument("--von", help="Wer hat geprueft")
    parser.add_argument("--stand", action="store_true", help="Stand anzeigen")
    parser.add_argument("--arbeitsliste", action="store_true",
                        help="VERIFIKATION.md erzeugen")
    parser.add_argument("--zuruecksetzen", action="store_true",
                        help="Flags wieder auf false setzen")
    args = parser.parse_args()

    if args.arbeitsliste:
        arbeitsliste_schreiben()
        return 0
    if args.stand or not args.kennungen:
        stand_zeigen()
        return 0

    if not args.zuruecksetzen and not args.von:
        print("Bitte --von angeben. Ein Verifikationsvermerk ohne Namen ist wertlos.")
        return 1

    kennungen = [k.upper() for k in args.kennungen]
    geaendert, unbekannt = _setzen(kennungen, not args.zuruecksetzen, args.von)

    if unbekannt:
        print("Unbekannte IDs: " + " ".join(unbekannt))
    if geaendert:
        wort = "zurueckgesetzt" if args.zuruecksetzen else "als verifiziert vermerkt"
        print(f"{len(geaendert)} {wort}: " + " ".join(geaendert))
    print()
    stand_zeigen()
    return 0 if not unbekannt else 1


if __name__ == "__main__":
    sys.exit(main())
