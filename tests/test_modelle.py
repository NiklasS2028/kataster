"""Prueft Datenhaltung, Historisierung und den Begruendungszwang."""

from __future__ import annotations

import sqlite3

import pytest


# v1-Schema der organisation-Tabelle, wortgleich zum Stand vor Phase 7. Bewusst
# als roher DDL-String und nicht ueber Datenbank(), damit die neuen Spalten
# NICHT schon durch CREATE TABLE entstehen. Sonst liefe der ALTER-Pfad nie und
# der Migrationstest waere aus dem falschen Grund gruen.
_V1_SCHEMA = """
CREATE TABLE schema_info (version INTEGER NOT NULL, angelegt_am TEXT NOT NULL);
INSERT INTO schema_info (version, angelegt_am) VALUES (1, '2025-01-01T00:00:00');
CREATE TABLE organisation (
    id                  INTEGER PRIMARY KEY CHECK (id = 1),
    name                TEXT,
    rechtsform          TEXT,
    beschaeftigte       INTEGER,
    ist_behoerde        INTEGER NOT NULL DEFAULT 0,
    erbringt_oeff_dienste INTEGER NOT NULL DEFAULT 0,
    ansprechpartner     TEXT,
    geaendert_am        TEXT
);
INSERT INTO organisation (id, name, beschaeftigte, geaendert_am)
    VALUES (1, 'Bestandsbau GmbH', 12, '2025-01-01T00:00:00');
"""


def _v1_datenbank_anlegen(pfad):
    con = sqlite3.connect(pfad)
    con.executescript(_V1_SCHEMA)
    con.commit()
    con.close()


def test_migration_v1_ergaenzt_organisationsspalten(tmp_path):
    """Eine v1-DB ohne die neuen Spalten muss den ALTER-Pfad durchlaufen.

    Gegenprobe: Kommentiert man in modelle._migrieren die beiden ALTER-Zeilen
    aus, faellt dieser Test rot. Damit testet er den Migrationscode und nicht
    nur das CREATE TABLE eines frischen Schemas."""
    from app.modelle import Datenbank, SCHEMA_VERSION

    pfad = tmp_path / "alt.sqlite"
    _v1_datenbank_anlegen(pfad)

    # Vor der Migration fehlen die Spalten wirklich.
    con = sqlite3.connect(pfad)
    spalten_vorher = {z[1] for z in con.execute("PRAGMA table_info(organisation)")}
    con.close()
    assert "groessenklasse" not in spalten_vorher
    assert "hat_partner_oder_verbund" not in spalten_vorher

    # Oeffnen fuehrt die Migration aus.
    db = Datenbank(pfad)
    with db.verbindung() as con:
        spalten = {z[1] for z in con.execute("PRAGMA table_info(organisation)")}
        version = con.execute("SELECT MAX(version) FROM schema_info").fetchone()[0]

    assert "groessenklasse" in spalten
    assert "hat_partner_oder_verbund" in spalten
    assert version == SCHEMA_VERSION


def test_migration_erhaelt_bestandsdaten(tmp_path):
    """Die Migration darf vorhandene Angaben nicht verlieren; neue Spalten
    starten leer bzw. mit ihrem Default."""
    from app.modelle import Datenbank

    pfad = tmp_path / "alt.sqlite"
    _v1_datenbank_anlegen(pfad)
    db = Datenbank(pfad)

    org = db.organisation_lesen()
    assert org["name"] == "Bestandsbau GmbH"
    assert org["beschaeftigte"] == 12
    assert org["groessenklasse"] is None
    assert org["hat_partner_oder_verbund"] == 0


def test_groessenklasse_und_verbund_werden_gespeichert(datenbank):
    datenbank.organisation_speichern(
        groessenklasse="kleines_midcap", hat_partner_oder_verbund=1)
    org = datenbank.organisation_lesen()
    assert org["groessenklasse"] == "kleines_midcap"
    assert org["hat_partner_oder_verbund"] == 1


def test_schema_wird_angelegt(datenbank):
    with datenbank.verbindung() as con:
        tabellen = {z["name"] for z in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"system", "flag", "einstufung", "nachweis",
            "organisation", "ausnahmeentscheidung"} <= tabellen


def test_organisation_ist_einzeilig(datenbank):
    datenbank.organisation_speichern(name="Musterbau GmbH")
    datenbank.organisation_speichern(name="Anders GmbH")
    with datenbank.verbindung() as con:
        assert con.execute("SELECT COUNT(*) FROM organisation").fetchone()[0] == 1
    assert datenbank.organisation_lesen()["name"] == "Anders GmbH"


def test_system_anlegen_und_lesen(datenbank):
    sid = datenbank.system_anlegen("ChatGPT", zweck="Texte",
                                   datenkategorien=["personenbezogen"])
    system = datenbank.system_lesen(sid)
    assert system["name"] == "ChatGPT"
    assert system["datenkategorien"] == ["personenbezogen"]
    assert system["status"] == "in_pruefung"


def test_flags_werden_ueberschrieben_nicht_gedoppelt(datenbank):
    sid = datenbank.system_anlegen("Testsystem")
    datenbank.flag_setzen(sid, "personalauswahl", True)
    datenbank.flag_setzen(sid, "personalauswahl", False)
    assert datenbank.flags_lesen(sid) == {"personalauswahl": False}


def test_einstufungen_werden_historisiert(datenbank, regelwerk):
    sid = datenbank.system_anlegen("Testsystem")
    for _ in range(3):
        datenbank.einstufung_speichern(
            sid, regelwerk.als_dict(regelwerk.einstufen({"personalauswahl": True})))
    assert len(datenbank.einstufung_historie(sid)) == 3


def test_aktuelle_einstufung_ist_die_neueste(datenbank, regelwerk):
    sid = datenbank.system_anlegen("Testsystem")
    datenbank.einstufung_speichern(sid, regelwerk.als_dict(regelwerk.einstufen({})))
    datenbank.einstufung_speichern(
        sid, regelwerk.als_dict(regelwerk.einstufen({"personalauswahl": True})))
    assert datenbank.einstufung_aktuell(sid)["klasse"] == "hochrisiko"


def test_einstufung_traegt_regelwerks_hash(datenbank, regelwerk):
    sid = datenbank.system_anlegen("Testsystem")
    datenbank.einstufung_speichern(sid, regelwerk.als_dict(regelwerk.einstufen({})))
    gespeichert = datenbank.einstufung_aktuell(sid)
    assert gespeichert["regelwerk_hash"] == regelwerk.hash()
    assert gespeichert["rechtsstand"] == regelwerk.rechtsstand


def test_ausnahme_ohne_begruendung_wird_abgewiesen(datenbank):
    sid = datenbank.system_anlegen("Testsystem")
    with pytest.raises(ValueError):
        datenbank.ausnahme_dokumentieren(sid, "E-01", "   ")
    assert datenbank.ausnahmen_lesen(sid) == []


def test_loeschen_raeumt_abhaengige_daten_ab(datenbank, regelwerk):
    sid = datenbank.system_anlegen("Testsystem")
    datenbank.flag_setzen(sid, "personalauswahl", True)
    datenbank.einstufung_speichern(sid, regelwerk.als_dict(regelwerk.einstufen({})))
    datenbank.ausnahme_dokumentieren(sid, "E-01", "Begruendung")
    datenbank.system_loeschen(sid)

    with datenbank.verbindung() as con:
        for tabelle in ("flag", "einstufung", "ausnahmeentscheidung"):
            anzahl = con.execute(
                f"SELECT COUNT(*) FROM {tabelle} WHERE system_id = ?", (sid,)
            ).fetchone()[0]
            assert anzahl == 0, f"{tabelle} nicht abgeraeumt"


def test_kennzahlen_zaehlen_nur_die_neueste_einstufung(datenbank, regelwerk):
    sid = datenbank.system_anlegen("Testsystem")
    datenbank.einstufung_speichern(
        sid, regelwerk.als_dict(regelwerk.einstufen({"personalauswahl": True})))
    datenbank.einstufung_speichern(sid, regelwerk.als_dict(regelwerk.einstufen({})))
    kennzahlen = datenbank.kennzahlen()
    assert kennzahlen["nach_klasse"] == {"minimal": 1}


def test_kosten_werden_summiert(datenbank):
    datenbank.system_anlegen("A", kosten_monat_eur=24.90)
    datenbank.system_anlegen("B", kosten_monat_eur=249.00)
    kennzahlen = datenbank.kennzahlen()
    assert kennzahlen["kosten_monat_eur"] == pytest.approx(273.90)
    assert kennzahlen["kosten_jahr_eur"] == pytest.approx(3286.80)
