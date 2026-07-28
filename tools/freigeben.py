#!/usr/bin/env python3
"""
freigeben.py - Hebt das Regelwerk auf eine Freigabeversion.

Der Zusatz "entwurf" in der Versionsnummer und der Verifikationsstand muessen
zusammenpassen. Ein Regelwerk, das "0.4.1-entwurf" heisst und gleichzeitig
"25/25 verifiziert" meldet, widerspricht sich - und wer das sieht, haelt
entweder die Versionsnummer oder die Verifikation fuer unglaubwuerdig.

Dieses Werkzeug prueft deshalb erst, ob jede Regel einen Pruefvermerk traegt,
und aendert die Versionsnummer nur dann. Es schreibt zeilenweise als Text,
damit Kommentare und bestehende Pruefvermerke unangetastet bleiben.

    python tools/freigeben.py --pruefen
    python tools/freigeben.py 1.0.0 --von "Niklas Steinhauser"
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import date
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
REGELWERK = WURZEL / "rules" / "ai-act_2026-07-23.yaml"

VERSION_ZEILE = re.compile(r'^(\s*regelwerk_version:\s*)"([^"]+)"\s*$')
HISTORIE_ANKER = "  aenderungshistorie:"


def _laden() -> list[str]:
    if not REGELWERK.exists():
        sys.exit(f"Regelwerk nicht gefunden: {REGELWERK}")
    return REGELWERK.read_text(encoding="utf-8").splitlines(keepends=True)


def _speichern(zeilen: list[str]) -> None:
    temp = REGELWERK.with_suffix(REGELWERK.suffix + ".tmp")
    temp.write_text("".join(zeilen), encoding="utf-8")
    temp.replace(REGELWERK)


def _stand() -> tuple[int, int, list[str], str]:
    """(verifiziert, gesamt, offene IDs, aktuelle Version)"""
    import yaml
    daten = yaml.safe_load(REGELWERK.read_text(encoding="utf-8"))
    regeln = daten.get("regeln", [])
    offen = [r["id"] for r in regeln if r.get("geprueft") is not True]
    version = daten.get("meta", {}).get("regelwerk_version", "?")
    return len(regeln) - len(offen), len(regeln), offen, version


def pruefen() -> int:
    verifiziert, gesamt, offen, version = _stand()
    print(f"Version:     {version}")
    print(f"Verifiziert: {verifiziert} von {gesamt}")

    entwurf = "entwurf" in version.lower()
    vollstaendig = not offen

    if offen:
        print("Offen:       " + " ".join(offen))

    if vollstaendig and entwurf:
        print()
        print("Widerspruch: Alle Regeln sind verifiziert, die Version traegt")
        print("aber noch den Zusatz 'entwurf'. Freigabe empfohlen.")
        return 1
    if not vollstaendig and not entwurf:
        print()
        print("Widerspruch: Die Version traegt keinen Entwurfszusatz, es sind")
        print("aber noch Regeln unverifiziert. Das ist die gefaehrlichere")
        print("Richtung - bitte korrigieren.")
        return 2
    print()
    print("Version und Verifikationsstand passen zusammen.")
    return 0


def freigeben(neue_version: str, von: str) -> int:
    verifiziert, gesamt, offen, alte_version = _stand()
    if offen:
        print(f"Freigabe nicht moeglich: {len(offen)} von {gesamt} Regeln sind")
        print("nicht verifiziert.")
        print("Offen: " + " ".join(offen))
        return 1

    if "entwurf" in neue_version.lower():
        print("Eine Freigabeversion sollte keinen Entwurfszusatz tragen.")
        return 1

    zeilen = _laden()
    heute = date.today().isoformat()
    geaendert = False

    for nummer, zeile in enumerate(zeilen):
        treffer = VERSION_ZEILE.match(zeile)
        if treffer:
            zeilen[nummer] = f'{treffer.group(1)}"{neue_version}"\n'
            geaendert = True
            break

    if not geaendert:
        print("Versionszeile nicht gefunden.")
        return 1

    # Historieneintrag direkt unter dem Anker einfuegen, damit er als erster
    # steht - so ist die juengste Aenderung ohne Scrollen sichtbar.
    eintrag = (
        f'    - datum: "{heute}"\n'
        f'      version: "{neue_version}"\n'
        f'      aenderung: >-\n'
        f'        Freigabe. Alle {gesamt} Regeln sind gegen den amtlichen Text der\n'
        f'        Verordnung (EU) 2024/1689 verifiziert, geprueft von {von}. Der\n'
        f'        Entwurfszusatz entfaellt. Offen bleibt allein die Omnibus-Lesart:\n'
        f'        Der Aenderungsrechtsakt lag zum Rechtsstand nicht im Amtsblatt\n'
        f'        vor, das Feld lesarten.omnibus.amtsblatt ist weiterhin null. Wer\n'
        f'        diese Lesart nutzt, muss sie zuvor gegen den veroeffentlichten\n'
        f'        Text pruefen.\n'
    )
    for nummer, zeile in enumerate(zeilen):
        if zeile.rstrip("\n") == HISTORIE_ANKER:
            zeilen.insert(nummer + 1, eintrag)
            break
    else:
        print("Abschnitt aenderungshistorie nicht gefunden.")
        return 1

    _speichern(zeilen)
    print(f"Freigegeben: {alte_version}  ->  {neue_version}")
    print(f"  {gesamt} Regeln verifiziert, Historieneintrag ergaenzt.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Regelwerk freigeben")
    parser.add_argument("version", nargs="?", help="Neue Version, etwa 1.0.0")
    parser.add_argument("--von", help="Wer hat verifiziert")
    parser.add_argument("--pruefen", action="store_true",
                        help="Nur pruefen, nichts aendern")
    args = parser.parse_args()

    if args.pruefen or not args.version:
        return pruefen()
    if not args.von:
        print("Bitte --von angeben.")
        return 1
    return freigeben(args.version, args.von)


if __name__ == "__main__":
    sys.exit(main())
