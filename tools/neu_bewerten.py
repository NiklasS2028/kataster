#!/usr/bin/env python3
"""
neu_bewerten.py - Rechnet alle Einstufungen mit dem aktuellen Regelwerk neu.

Noetig, wenn sich das Regelwerk geaendert hat. Die alten Einstufungen bleiben
erhalten - jede Neuberechnung legt einen zusaetzlichen Datensatz an. Der
Fortfuehrungsnachweis zeigt danach beide Staende nebeneinander.

    python tools/neu_bewerten.py --pruefen
    python tools/neu_bewerten.py
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL))

from app.modelle import Datenbank            # noqa: E402
from app.regelwerk import Regelwerk          # noqa: E402

DATENBANK = WURZEL / "kataster.sqlite"
REGELWERK = WURZEL / "rules" / "ai-act_2026-07-27.yaml"


def _lage(db: Datenbank, rw: Regelwerk):
    systeme = db.systeme_auflisten()
    veraltet, aktuell, ohne = [], [], []
    for s in systeme:
        e = db.einstufung_aktuell(s["id"])
        if not e:
            ohne.append(s)
        elif e["regelwerk_version"] != rw.version:
            veraltet.append((s, e))
        else:
            aktuell.append(s)
    return systeme, veraltet, aktuell, ohne


def main() -> int:
    if not DATENBANK.exists():
        print("Keine Datenbank gefunden.")
        return 1

    db = Datenbank(DATENBANK)
    rw = Regelwerk.laden(REGELWERK)
    systeme, veraltet, aktuell, ohne = _lage(db, rw)

    print(f"Regelwerk: {rw.version}")
    print(f"Systeme:   {len(systeme)}")
    print(f"  aktuell:      {len(aktuell)}")
    print(f"  veraltet:     {len(veraltet)}")
    print(f"  nie bewertet: {len(ohne)}")

    if veraltet:
        print()
        for s, e in veraltet:
            print(f"  {s['name'][:40]:<40} {e['regelwerk_version']}")

    if "--pruefen" in sys.argv:
        return 0
    if not veraltet:
        print()
        print("Nichts zu tun.")
        return 0

    org = db.organisation_lesen()
    print()
    for s, alt in veraltet:
        seit = None
        if s.get("in_betrieb_seit"):
            try:
                seit = date.fromisoformat(s["in_betrieb_seit"])
            except ValueError:
                pass
        neu = rw.einstufen(
            db.flags_lesen(s["id"]),
            rolle=s["rolle"],
            in_betrieb_seit=seit,
            wesentlich_veraendert=bool(s.get("wesentlich_veraendert_am")),
            ist_behoerde=bool(org.get("ist_behoerde")),
        )
        db.einstufung_speichern(s["id"], rw.als_dict(neu))
        pfeil = "  " if alt["klasse"] == neu.klasse else "->"
        print(f"  {s['name'][:34]:<34} {alt['klasse']:<12} {pfeil} {neu.klasse}")

    print()
    print(f"{len(veraltet)} Einstufungen neu berechnet. Alte Staende bleiben")
    print("im Fortfuehrungsnachweis erhalten.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
