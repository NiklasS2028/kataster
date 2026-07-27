#!/usr/bin/env python3
"""
zeit.py - Zeiterfassung fuer das Projekt Kataster.

Bewusst ohne externe Abhaengigkeiten und ohne Sonderzeichen in der Ausgabe,
damit es unter Windows PowerShell 5.1 (cp1252) sauber laeuft.

    python tools/zeit.py start "Regelwerk YAML" --phase regelwerk
    python tools/zeit.py status
    python tools/zeit.py stop
    python tools/zeit.py log
    python tools/zeit.py report
    python tools/zeit.py report --md ZEITBILANZ.md

Datenhaltung: .zeit/sessions.jsonl (eine Zeile pro Sitzung, append-only).
Die laufende Sitzung liegt separat in .zeit/laufend.json.
"""

import argparse
import json
import os
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timedelta

BASIS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".zeit")
SESSIONS = os.path.join(BASIS, "sessions.jsonl")
LAUFEND = os.path.join(BASIS, "laufend.json")

PHASEN = [
    "recherche", "regelwerk", "backend", "frontend",
    "export", "tests", "doku", "release", "sonstiges",
]


# --------------------------------------------------------------------------
# Hilfsfunktionen
# --------------------------------------------------------------------------

def _sicherstellen():
    os.makedirs(BASIS, exist_ok=True)


def _jetzt():
    return datetime.now().replace(microsecond=0)


def _lesen_laufend():
    if not os.path.exists(LAUFEND):
        return None
    with open(LAUFEND, "r", encoding="utf-8") as f:
        return json.load(f)


def _schreiben_laufend(daten):
    with open(LAUFEND, "w", encoding="utf-8") as f:
        json.dump(daten, f, ensure_ascii=False, indent=2)


def _anhaengen_session(daten):
    with open(SESSIONS, "a", encoding="utf-8") as f:
        f.write(json.dumps(daten, ensure_ascii=False) + "\n")


def _lesen_sessions():
    if not os.path.exists(SESSIONS):
        return []
    eintraege = []
    with open(SESSIONS, "r", encoding="utf-8") as f:
        for zeile in f:
            zeile = zeile.strip()
            if zeile:
                eintraege.append(json.loads(zeile))
    return eintraege


def _dauer_lesbar(minuten):
    stunden, rest = divmod(int(round(minuten)), 60)
    return "{}h {:02d}min".format(stunden, rest)


def _git(*args):
    """Git-Aufruf, der bei fehlendem Repo einfach None liefert."""
    try:
        ausgabe = subprocess.check_output(
            ["git"] + list(args),
            stderr=subprocess.DEVNULL,
            cwd=os.path.join(BASIS, ".."),
        )
        return ausgabe.decode("utf-8", errors="replace").strip()
    except Exception:
        return None


# --------------------------------------------------------------------------
# Befehle
# --------------------------------------------------------------------------

def befehl_start(args):
    _sicherstellen()
    if _lesen_laufend():
        print("Es laeuft bereits eine Sitzung. Erst 'stop' aufrufen.")
        return 1

    beschreibung = args.beschreibung or "ohne Beschreibung"
    _schreiben_laufend({
        "start": _jetzt().isoformat(),
        "beschreibung": beschreibung,
        "phase": args.phase,
    })
    print("Gestartet um {}: {} [{}]".format(
        _jetzt().strftime("%H:%M"), beschreibung, args.phase))
    return 0


def befehl_stop(args):
    _sicherstellen()
    laufend = _lesen_laufend()
    if not laufend:
        print("Keine laufende Sitzung.")
        return 1

    start = datetime.fromisoformat(laufend["start"])
    ende = _jetzt()
    minuten = (ende - start).total_seconds() / 60.0

    if minuten < 1:
        print("Sitzung kuerzer als eine Minute - wird verworfen.")
        os.remove(LAUFEND)
        return 0

    _anhaengen_session({
        "start": laufend["start"],
        "ende": ende.isoformat(),
        "minuten": round(minuten, 1),
        "beschreibung": laufend["beschreibung"],
        "phase": laufend["phase"],
        "notiz": args.notiz or "",
    })
    os.remove(LAUFEND)
    print("Beendet. Dauer: {} ({})".format(
        _dauer_lesbar(minuten), laufend["beschreibung"]))
    return 0


def befehl_status(args):
    laufend = _lesen_laufend()
    if not laufend:
        print("Keine laufende Sitzung.")
        return 0
    start = datetime.fromisoformat(laufend["start"])
    minuten = (_jetzt() - start).total_seconds() / 60.0
    print("Laeuft seit {} - {} [{}]".format(
        start.strftime("%H:%M"), _dauer_lesbar(minuten), laufend["phase"]))
    print("Aufgabe: {}".format(laufend["beschreibung"]))
    return 0


def befehl_log(args):
    sessions = _lesen_sessions()
    if not sessions:
        print("Noch keine Sitzungen erfasst.")
        return 0
    for s in sessions[-args.anzahl:]:
        start = datetime.fromisoformat(s["start"])
        print("{}  {:>8}  {:<12}  {}".format(
            start.strftime("%Y-%m-%d %H:%M"),
            _dauer_lesbar(s["minuten"]),
            s["phase"],
            s["beschreibung"],
        ))
    return 0


def _kennzahlen(sessions):
    gesamt = sum(s["minuten"] for s in sessions)
    tage = sorted({datetime.fromisoformat(s["start"]).date() for s in sessions})

    nach_phase = defaultdict(float)
    for s in sessions:
        nach_phase[s["phase"]] += s["minuten"]

    nach_tag = defaultdict(float)
    for s in sessions:
        nach_tag[datetime.fromisoformat(s["start"]).date()] += s["minuten"]

    spanne = 0
    if tage:
        spanne = (tage[-1] - tage[0]).days + 1

    return {
        "gesamt_minuten": gesamt,
        "sitzungen": len(sessions),
        "arbeitstage": len(tage),
        "kalendertage": spanne,
        "erste": tage[0] if tage else None,
        "letzte": tage[-1] if tage else None,
        "schnitt_sitzung": gesamt / len(sessions) if sessions else 0,
        "schnitt_tag": gesamt / len(tage) if tage else 0,
        "laengste": max((s["minuten"] for s in sessions), default=0),
        "nach_phase": dict(nach_phase),
        "nach_tag": dict(nach_tag),
    }


def befehl_report(args):
    sessions = _lesen_sessions()
    if not sessions:
        print("Noch keine Sitzungen erfasst.")
        return 0

    k = _kennzahlen(sessions)
    commits = _git("rev-list", "--count", "HEAD")
    dateien = _git("ls-files")
    dateizahl = len(dateien.splitlines()) if dateien else None

    zeilen = []
    zeilen.append("# Zeitbilanz Kataster")
    zeilen.append("")
    zeilen.append("Stand: {}".format(_jetzt().strftime("%Y-%m-%d %H:%M")))
    zeilen.append("")
    zeilen.append("## Kennzahlen")
    zeilen.append("")
    zeilen.append("| Kennzahl | Wert |")
    zeilen.append("|---|---|")
    zeilen.append("| Gesamtaufwand | {} |".format(_dauer_lesbar(k["gesamt_minuten"])))
    zeilen.append("| Sitzungen | {} |".format(k["sitzungen"]))
    zeilen.append("| Arbeitstage | {} |".format(k["arbeitstage"]))
    zeilen.append("| Zeitraum | {} bis {} ({} Kalendertage) |".format(
        k["erste"], k["letzte"], k["kalendertage"]))
    zeilen.append("| Schnitt je Sitzung | {} |".format(_dauer_lesbar(k["schnitt_sitzung"])))
    zeilen.append("| Schnitt je Arbeitstag | {} |".format(_dauer_lesbar(k["schnitt_tag"])))
    zeilen.append("| Laengste Sitzung | {} |".format(_dauer_lesbar(k["laengste"])))
    if commits:
        zeilen.append("| Commits | {} |".format(commits))
    if dateizahl:
        zeilen.append("| Versionierte Dateien | {} |".format(dateizahl))
    zeilen.append("")
    zeilen.append("## Aufwand nach Phase")
    zeilen.append("")
    zeilen.append("| Phase | Aufwand | Anteil |")
    zeilen.append("|---|---|---|")
    for phase, minuten in sorted(k["nach_phase"].items(),
                                 key=lambda x: -x[1]):
        anteil = 100.0 * minuten / k["gesamt_minuten"]
        zeilen.append("| {} | {} | {:.0f} % |".format(
            phase, _dauer_lesbar(minuten), anteil))
    zeilen.append("")
    zeilen.append("## Aufwand nach Tag")
    zeilen.append("")
    zeilen.append("| Datum | Aufwand |")
    zeilen.append("|---|---|")
    for tag, minuten in sorted(k["nach_tag"].items()):
        zeilen.append("| {} | {} |".format(tag, _dauer_lesbar(minuten)))
    zeilen.append("")
    zeilen.append("_Erhoben mit tools/zeit.py. Nur aktiv erfasste Zeit, "
                  "keine Schaetzungen._")

    text = "\n".join(zeilen)

    if args.md:
        ziel = os.path.join(BASIS, "..", args.md)
        with open(ziel, "w", encoding="utf-8") as f:
            f.write(text + "\n")
        print("Geschrieben: {}".format(os.path.normpath(ziel)))
    else:
        print(text)
    return 0


# --------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Zeiterfassung Kataster")
    unter = parser.add_subparsers(dest="befehl")

    p = unter.add_parser("start", help="Sitzung beginnen")
    p.add_argument("beschreibung", nargs="?", help="Woran arbeitest du?")
    p.add_argument("--phase", default="sonstiges", choices=PHASEN)
    p.set_defaults(func=befehl_start)

    p = unter.add_parser("stop", help="Sitzung beenden")
    p.add_argument("--notiz", default="", help="Kurze Notiz zum Ergebnis")
    p.set_defaults(func=befehl_stop)

    p = unter.add_parser("status", help="Laufende Sitzung anzeigen")
    p.set_defaults(func=befehl_status)

    p = unter.add_parser("log", help="Letzte Sitzungen auflisten")
    p.add_argument("--anzahl", type=int, default=20)
    p.set_defaults(func=befehl_log)

    p = unter.add_parser("report", help="Auswertung erzeugen")
    p.add_argument("--md", help="Als Markdown-Datei schreiben")
    p.set_defaults(func=befehl_report)

    args = parser.parse_args()
    if not args.befehl:
        parser.print_help()
        return 0
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
