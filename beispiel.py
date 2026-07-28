#!/usr/bin/env python3
"""
beispiel.py - Legt einen Musterbestand an.

Damit sieht man in einer Minute, was Kataster tut, statt erst zehn Systeme
erfassen zu muessen.

Der Bestand ist bewusst so gewaehlt, dass alle vier Risikoklassen vorkommen
und die schwierigen Faelle sichtbar werden: der Anhang-I-Pfad ueber ein
Maschinensteuerungsmodul, der Bestandsschutz nach Art. 111 bei einem
Altsystem, eine dokumentierte Ausnahme nach Art. 6 Abs. 3, und drei
Werkzeuge, die erst ueber die anonyme Umfrage aufgetaucht sind.

Die Daten entstehen ueber dieselben Codepfade wie im Betrieb: Flags werden
gesetzt, das Regelwerk stuft ein, das Ergebnis wird historisiert. Nichts wird
von Hand in die Tabellen geschrieben - sonst zeigte die Demo etwas, das die
Anwendung so gar nicht erzeugen kann.

    python beispiel.py           legt an, bricht ab wenn schon Daten da sind
    python beispiel.py --neu     loescht den vorhandenen Bestand vorher
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

WURZEL = Path(__file__).resolve().parent
sys.path.insert(0, str(WURZEL))

from app.modelle import Datenbank            # noqa: E402
from app.regelwerk import Regelwerk          # noqa: E402

DATENBANK = WURZEL / "kataster.sqlite"
REGELWERK = WURZEL / "rules" / "ai-act_2026-07-23.yaml"


ORGANISATION = {
    "name": "Musterbau Anlagentechnik GmbH",
    "rechtsform": "GmbH",
    "beschaeftigte": 42,
    "ansprechpartner": "Andrea Weber, Kaufmaennische Leitung",
    "ist_behoerde": 0,
    "erbringt_oeff_dienste": 0,
}


# (Stammdaten, Flags, Rolle, Zusatzangaben)
SYSTEME = [
    (
        {
            "name": "ChatGPT Team",
            "anbieter": "OpenAI",
            "zweck": "Angebotstexte entwerfen, E-Mails formulieren, Protokolle kuerzen",
            "abteilung": "Vertrieb",
            "verantwortlich": "Andrea Weber",
            "status": "freigegeben",
            "kosten_monat_eur": 250.00,
            "kostenstelle": "4711",
            "av_vertrag": 1,
            "eu_hosting": 0,
            "training_mit_eingaben": 0,
            "datenkategorien": ["kundendaten"],
            "in_betrieb_seit": "2025-03-01",
        },
        {},
        "betreiber",
        {},
    ),
    (
        {
            "name": "DeepL Pro",
            "anbieter": "DeepL SE",
            "zweck": "Technische Dokumentation ins Englische und Polnische",
            "abteilung": "Technische Redaktion",
            "verantwortlich": "Markus Ilic",
            "status": "freigegeben",
            "kosten_monat_eur": 59.90,
            "av_vertrag": 1,
            "eu_hosting": 1,
            "training_mit_eingaben": 0,
            "datenkategorien": ["geschaeftsgeheimnisse"],
            "in_betrieb_seit": "2023-09-15",
        },
        {},
        "betreiber",
        {},
    ),
    (
        {
            "name": "Bewerbermanagement Talentfilter",
            "anbieter": "Personio-Zusatzmodul",
            "zweck": "Eingehende Bewerbungen vorsortieren und nach Passung reihen",
            "abteilung": "Personal",
            "verantwortlich": "Sabine Krohn",
            "status": "geduldet",
            "kosten_monat_eur": 189.00,
            "kostenstelle": "4030",
            "av_vertrag": 1,
            "eu_hosting": 1,
            "training_mit_eingaben": 0,
            "datenkategorien": ["personenbezogen", "beschaeftigtendaten"],
            "in_betrieb_seit": "2024-05-01",
        },
        {"personalauswahl": True},
        "betreiber",
        {
            "ausnahme": (
                "E-04",
                "Das Modul erstellt ausschliesslich eine Vorsortierung nach "
                "formalen Kriterien (Abschluss, Berufsjahre, Fuehrerschein). "
                "Die Sichtung aller Bewerbungen und die Einladungsentscheidung "
                "trifft die Personalleitung; das Ergebnis der Reihung ist dabei "
                "nicht bindend und wird nicht angezeigt.",
                "Sabine Krohn",
            )
        },
    ),
    (
        {
            "name": "Zutrittskontrolle Werk II",
            "anbieter": "Sicherheitstechnik Nord",
            "zweck": "Gesichtserkennung am Tor zum Hochregallager",
            "abteilung": "Werkschutz",
            "verantwortlich": "Thomas Ade",
            "status": "in_pruefung",
            "kosten_monat_eur": 120.00,
            "av_vertrag": 0,
            "eu_hosting": 1,
            "datenkategorien": ["personenbezogen", "besondere_kategorien",
                                "beschaeftigtendaten"],
            "in_betrieb_seit": "2026-01-10",
        },
        {"biometrische_fernidentifizierung": True},
        "betreiber",
        {},
    ),
    (
        {
            "name": "Assistenzsteuerung Palettierroboter",
            "anbieter": "Eigenentwicklung",
            "zweck": "Erkennt Personen im Arbeitsbereich und drosselt den Antrieb",
            "abteilung": "Konstruktion",
            "verantwortlich": "Markus Ilic",
            "status": "in_pruefung",
            "kostenstelle": "2200",
            "eu_hosting": 1,
            "datenkategorien": ["keine"],
            "in_betrieb_seit": "2026-04-01",
        },
        {
            "anhang_i_sicherheitsbauteil": True,
            "anhang_i_dritte_konformitaetsbewertung": True,
        },
        "anbieter",
        {},
    ),
    (
        {
            "name": "Kundenportal-Assistent",
            "anbieter": "Eigenentwicklung auf Basis Azure OpenAI",
            "zweck": "Beantwortet Fragen zu Ersatzteilen im Kundenportal",
            "abteilung": "Service",
            "verantwortlich": "Andrea Weber",
            "status": "freigegeben",
            "kosten_monat_eur": 340.00,
            "kostenstelle": "5100",
            "av_vertrag": 1,
            "eu_hosting": 1,
            "datenkategorien": ["kundendaten"],
            "in_betrieb_seit": "2026-06-01",
        },
        {"direkte_interaktion": True},
        "anbieter",
        {},
    ),
    (
        {
            "name": "Stimmungsanalyse Servicetelefonie",
            "anbieter": "CallSense",
            "zweck": "Pilot: wertet die Stimmlage der Mitarbeitenden im "
                     "Kundengespraech aus und meldet Belastungsspitzen",
            "abteilung": "Service",
            "verantwortlich": "Thomas Ade",
            "status": "untersagt",
            "kosten_monat_eur": 0.00,
            "av_vertrag": 0,
            "datenkategorien": ["personenbezogen", "besondere_kategorien",
                                "beschaeftigtendaten"],
            "in_betrieb_seit": "2026-05-01",
        },
        {"emotionserkennung_arbeit_bildung": True},
        "betreiber",
        {},
    ),
    (
        {
            "name": "Kampagnenbilder Bildgenerator",
            "anbieter": "Adobe Firefly",
            "zweck": "Erzeugt Motive fuer Messeauftritte und Social Media",
            "abteilung": "Marketing",
            "verantwortlich": "Lena Ruf",
            "status": "freigegeben",
            "kosten_monat_eur": 34.99,
            "av_vertrag": 1,
            "eu_hosting": 0,
            "datenkategorien": ["keine"],
            "in_betrieb_seit": "2026-02-01",
        },
        {"deepfake": True},
        "betreiber",
        {},
    ),
]


# Aus der anonymen Umfrage aufgetaucht, noch nicht bewertet.
AUS_UMFRAGE = [
    ("Microsoft Copilot", "Formeln in Excel, Zusammenfassungen", "IT", 7),
    ("Perplexity", "Recherche zu Lieferanten und Normen", "Einkauf", 3),
    ("Canva Magic Write", "Texte fuer Aushaenge und Stellenanzeigen", "Personal", 2),
]


def anlegen(neu: bool = False) -> None:
    if DATENBANK.exists() and not neu:
        vorhandene = Datenbank(DATENBANK).systeme_auflisten()
        if vorhandene:
            print(f"Es liegen bereits {len(vorhandene)} Systeme vor.")
            print("Mit  python beispiel.py --neu  wird der Bestand ersetzt.")
            return
    if neu and DATENBANK.exists():
        DATENBANK.unlink()
        print("Vorhandener Bestand geloescht.")

    db = Datenbank(DATENBANK)
    rw = Regelwerk.laden(REGELWERK)
    db.organisation_speichern(**ORGANISATION)

    for stammdaten, flags, rolle, extras in SYSTEME:
        system_id = db.system_anlegen(rolle=rolle, quelle="offiziell", **stammdaten)

        for name, wert in flags.items():
            db.flag_setzen(system_id, name, wert, stammdaten.get("verantwortlich"))

        seit = stammdaten.get("in_betrieb_seit")
        einstufung = rw.einstufen(
            db.flags_lesen(system_id),
            rolle=rolle,
            in_betrieb_seit=date.fromisoformat(seit) if seit else None,
            ist_behoerde=bool(ORGANISATION["ist_behoerde"]),
        )
        db.einstufung_speichern(system_id, rw.als_dict(einstufung))

        if "ausnahme" in extras:
            bedingung, begruendung, person = extras["ausnahme"]
            db.ausnahme_dokumentieren(system_id, bedingung, begruendung, person)

    for name, zweck, bereich, nennungen in AUS_UMFRAGE:
        db.system_anlegen(
            name=name, zweck=zweck, abteilung=bereich,
            quelle="schatten_gemeldet", status="in_pruefung",
            notiz=f"Aus anonymer Umfrage, {nennungen} Nennung(en).",
        )

    _bericht(db, rw)


def _bericht(db: Datenbank, rw: Regelwerk) -> None:
    kennzahlen = db.kennzahlen()
    bezeichnungen = {k: v.get("bezeichnung", k) for k, v in rw.risikoklassen.items()}

    print()
    print(f"Musterbestand angelegt: {ORGANISATION['name']}")
    print(f"  {kennzahlen['systeme_gesamt']} Systeme, davon "
          f"{kennzahlen['nach_quelle'].get('schatten_gemeldet', 0)} aus der Umfrage")
    print()
    for schluessel in sorted(rw.risikoklassen,
                             key=lambda k: -rw.risikoklassen[k]["rang"]):
        anzahl = kennzahlen["nach_klasse"].get(schluessel, 0)
        if anzahl:
            print(f"  {anzahl:>2}  {bezeichnungen[schluessel]}")
    if kennzahlen["ohne_einstufung"]:
        print(f"  {kennzahlen['ohne_einstufung']:>2}  noch nicht eingestuft")
    print()
    print(f"  Aufwand: {kennzahlen['kosten_monat_eur']:.2f} EUR monatlich, "
          f"{kennzahlen['kosten_jahr_eur']:.2f} EUR im Jahr")
    print()
    print("  python start.py   und dann http://127.0.0.1:8771")


if __name__ == "__main__":
    anlegen(neu="--neu" in sys.argv)
