"""Prueft Datenhaltung, Historisierung und den Begruendungszwang."""

from __future__ import annotations

import pytest


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
