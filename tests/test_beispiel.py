"""Smoke-Test fuer beispiel.py.

beispiel.py ist das Erste, was jemand ausfuehrt, der das Projekt ansieht; ein
Bruch dort ist teurer als anderswo. Der Test laeuft gegen eine temporaere DB
(Monkeypatch von beispiel.DATENBANK), nicht gegen den ausgelieferten Bestand.
"""

from __future__ import annotations

from datetime import datetime

import pytest


@pytest.fixture
def musterbestand(tmp_path, monkeypatch):
    import beispiel
    from app.modelle import Datenbank

    monkeypatch.setattr(beispiel, "DATENBANK", tmp_path / "beispiel.sqlite")
    beispiel.anlegen(neu=True)
    return Datenbank(tmp_path / "beispiel.sqlite")


def test_durchlauf_legt_zwoelf_systeme_an(musterbestand):
    kennzahlen = musterbestand.kennzahlen()
    assert kennzahlen["systeme_gesamt"] == 12


def test_erwartete_klassenverteilung(musterbestand):
    """Neun bewertete Systeme plus drei aus der Umfrage (unbewertet). Die
    Verteilung haelt die Aussage der Demo fest: alle vier Risikoklassen kommen
    vor, der Moodboard-Generator ist der minimale Gegenfall zum Firefly-Deepfake."""
    nach_klasse = musterbestand.kennzahlen()["nach_klasse"]
    assert nach_klasse == {
        "verboten": 1,
        "hochrisiko": 3,
        "transparenz": 2,
        "minimal": 3,
    }
    assert musterbestand.kennzahlen()["ohne_einstufung"] == 3


def test_palettierroboter_faellt_unter_abschnitt_b_ohne_warnung(musterbestand):
    """Der Anhang-I-Abschnitt-B-Pfad greift, die Klasse bleibt hochrisiko, und es
    feuert keine Unbekanntes-Flag-Warnung (Flag ist registriert)."""
    treffer = next(
        s for s in musterbestand.systeme_auflisten() if "Palettier" in s["name"]
    )
    ergebnis = musterbestand.einstufung_aktuell(treffer["id"])["ergebnis"]
    assert ergebnis["klasse"] == "hochrisiko"
    assert ergebnis["abschnitt_b_greift"] is True
    assert ergebnis["warnungen"] == []


def test_dossier_abschnitt_vier_nicht_leer(musterbestand):
    """Mit gesetzter Groessenklasse zeigt Abschnitt 4 Erleichterungen statt des
    Leerhinweises."""
    from app.regelwerk import Regelwerk
    from app.export.dossier import dossier_html
    from tests.conftest import REGELWERK_PFAD

    rw = Regelwerk.laden(REGELWERK_PFAD)
    org = musterbestand.organisation_lesen()
    systeme = musterbestand.systeme_auflisten()
    for s in systeme:
        s["einstufung"] = musterbestand.einstufung_aktuell(s["id"])
    klassennamen = {k: v.get("bezeichnung", k) for k, v in rw.risikoklassen.items()}
    html = dossier_html(
        org, systeme, musterbestand.kennzahlen(), rw, klassennamen,
        datetime(2026, 7, 31, 12, 0),
    )
    assert "keine Groessenklasse" not in html
    assert "Vereinfachtes Qualitaetsmanagement" in html  # G-04, mit Vorbehalt
