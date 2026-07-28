"""Prueft den Fragefluss: Kontextfilter, Rollenfilter, Ausstiege."""

from __future__ import annotations

import pytest


@pytest.fixture
def wizard(regelwerk):
    from app.wizard import Wizard
    return Wizard(regelwerk)


def _durchlaufen(wizard, kontexte, ja=()):
    """Klickt den Bogen durch und gibt (Antworten, Anzahl Fragen) zurueck."""
    antworten, gestellt = {}, 0
    while (frage := wizard.naechste_frage(antworten)) and gestellt < 80:
        if frage.typ == "mehrfachauswahl":
            antworten[frage.schluessel] = list(kontexte)
        elif frage.typ == "datum":
            antworten[frage.schluessel] = None
        else:
            antworten[frage.schluessel] = frage.schluessel in ja
        gestellt += 1
    return antworten, gestellt


def test_erste_frage_ist_der_kontext(wizard):
    frage = wizard.naechste_frage({})
    assert frage.schluessel == "kontext"
    assert frage.typ == "mehrfachauswahl"


def test_ohne_kontext_keine_weiteren_fragen(wizard):
    assert len(wizard.alle_fragen({})) == 1


def test_kontext_kuerzt_den_bogen(wizard):
    _, wenige = _durchlaufen(wizard, ["interne_verwaltung"], ja=["rolle:R-01"])
    _, viele = _durchlaufen(wizard, ["personal", "biometrie", "inhalte",
                                     "kundenkontakt", "produkt"], ja=["rolle:R-01"])
    assert wenige < viele
    assert wenige <= 12, f"Buerowerkzeug braucht {wenige} Fragen - zu viele"


def test_alle_kontexte_stellen_alle_regelfragen(wizard, regelwerk):
    alle = [k["id"] for k in regelwerk.einsatzkontexte["definitionen"]]
    antworten, _ = _durchlaufen(wizard, alle, ja=["rolle:R-01"])
    ergebnis = wizard.auswerten(antworten)
    assert ergebnis.uebersprungene_regeln == []


def test_keine_doppelten_fragen(wizard, regelwerk):
    alle = [k["id"] for k in regelwerk.einsatzkontexte["definitionen"]]
    antworten, _ = _durchlaufen(wizard, alle, ja=["rolle:R-01"])
    schluessel = [f.schluessel for f in wizard.alle_fragen(antworten)]
    assert len(schluessel) == len(set(schluessel))


def test_uebersprungene_regeln_werden_ausgewiesen(wizard):
    antworten, _ = _durchlaufen(wizard, ["interne_verwaltung"], ja=["rolle:R-01"])
    ergebnis = wizard.auswerten(antworten)
    assert ergebnis.uebersprungene_regeln
    assert ergebnis.kontexte == ["interne_verwaltung"]


def test_privatnutzung_beendet_den_bogen(wizard):
    antworten = {"kontext": ["interne_verwaltung"], "ab:A-01": True}
    ergebnis = wizard.auswerten(antworten)
    assert ergebnis.ausserhalb_anwendungsbereich
    assert ergebnis.ausschluss_fundstelle


def test_rolle_wird_aus_antworten_abgeleitet(wizard):
    nur_betreiber, _ = _durchlaufen(wizard, ["kundenkontakt"], ja=["rolle:R-01"])
    assert wizard.auswerten(nur_betreiber).rolle == "betreiber"

    auch_anbieter, _ = _durchlaufen(wizard, ["kundenkontakt"],
                                    ja=["rolle:R-01", "rolle:R-02"])
    assert wizard.auswerten(auch_anbieter).rolle == "beides"


def test_transparenzfragen_nur_fuer_anbieter(wizard):
    betreiber, _ = _durchlaufen(wizard, ["inhalte"], ja=["rolle:R-01"])
    anbieter, _ = _durchlaufen(wizard, ["inhalte"], ja=["rolle:R-01", "rolle:R-02"])
    schluessel_b = {f.schluessel for f in wizard.alle_fragen(betreiber)}
    schluessel_a = {f.schluessel for f in wizard.alle_fragen(anbieter)}
    assert "flag:synthetische_inhalte" not in schluessel_b
    assert "flag:synthetische_inhalte" in schluessel_a


def test_bestandsfragen_nur_bei_hochrisiko(wizard):
    ohne, _ = _durchlaufen(wizard, ["interne_verwaltung"], ja=["rolle:R-01"])
    mit, _ = _durchlaufen(wizard, ["personal"],
                          ja=["rolle:R-01", "flag:personalauswahl"])
    assert not any(f.abschnitt == "bestand" for f in wizard.alle_fragen(ohne))
    assert any(f.abschnitt == "bestand" for f in wizard.alle_fragen(mit))


def test_fortschritt_zaehlt_richtig(wizard):
    antworten, gestellt = _durchlaufen(wizard, ["personal"], ja=["rolle:R-01"])
    beantwortet, gesamt = wizard.fortschritt(antworten)
    assert beantwortet == gesamt == gestellt
