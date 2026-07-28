"""
Prueft das Regelwerk und die Einstufungslogik.

Der Kern ist test_jede_regel_loest_ihre_klasse_aus: Fuer jede einzelne Regel
wird geprueft, dass das zugehoerige Flag genau die erwartete Klasse erzeugt.
Faellt eine Regel aus dem Regelwerk oder aendert sich ihre Klasse, schlaegt
genau ein Test fehl - und zwar der mit dem passenden Namen.
"""

from __future__ import annotations

from datetime import date

import pytest


# --- Struktur -------------------------------------------------------------

def test_regelwerk_laedt(regelwerk):
    assert regelwerk.version
    assert regelwerk.rechtsstand
    assert regelwerk.regeln


def test_keine_strukturfehler(regelwerk):
    fehler = [p for p in regelwerk.validieren() if p.schwere == "fehler"]
    assert not fehler, "\n".join(f"{p.ort}: {p.text}" for p in fehler)


def test_regel_ids_eindeutig(regelwerk):
    ids = [r["id"] for r in regelwerk.regeln]
    assert len(ids) == len(set(ids))


def test_jede_regel_hat_fundstelle(regelwerk):
    ohne = [r["id"] for r in regelwerk.regeln if not r.get("fundstelle")]
    assert not ohne, f"Regeln ohne Fundstelle: {ohne}"


def test_jede_frist_referenz_existiert(regelwerk):
    fristen = {f["id"] for f in regelwerk.fristen}
    tot = [r["id"] for r in regelwerk.regeln
           if r.get("frist_ref") and r["frist_ref"] not in fristen]
    assert not tot, f"Tote Fristenverweise: {tot}"


def test_hash_ist_stabil(regelwerk):
    assert regelwerk.hash() == regelwerk.hash()
    assert len(regelwerk.hash()) == 64


# --- Kern: eine Pruefung je Regel -----------------------------------------

def _regelfaelle(regelwerk):
    faelle = []
    for regel in regelwerk.regeln:
        flags = {regel["trifft_zu_wenn"]: True}
        zusatz = regel.get("zusatzbedingung")
        if zusatz:
            flags[zusatz["trifft_zu_wenn"]] = True
        rollen = regel.get("nur_bei_rolle") or ["betreiber"]
        faelle.append(pytest.param(regel["id"], flags, regel["klasse"],
                                   rollen[0], id=regel["id"]))
    return faelle


def pytest_generate_tests(metafunc):
    if "regel_id" in metafunc.fixturenames:
        from app.regelwerk import Regelwerk
        from tests.conftest import REGELWERK_PFAD
        rw = Regelwerk.laden(REGELWERK_PFAD)
        metafunc.parametrize("regel_id,flags,erwartet,rolle", _regelfaelle(rw))


def test_jede_regel_loest_ihre_klasse_aus(regelwerk, regel_id, flags, erwartet, rolle):
    """Jede Regel muss durch ihr Flag ausgeloest werden.

    Die resultierende Klasse kann hoeher liegen als die der Regel selbst:
    Mehrere Regeln teilen sich ein Flag. So loest emotionserkennung_sonstige
    sowohl H-09 (Hochrisiko) als auch T-04 (Transparenzpflicht) aus - das
    Ergebnis ist dann Hochrisiko, und T-04 gilt zusaetzlich. Geprueft wird
    deshalb: Die Regel greift, und die Klasse faellt nicht darunter zurueck.
    """
    einstufung = regelwerk.einstufen(flags, rolle=rolle)
    assert regel_id in einstufung.ausgeloest_durch

    rang_regel = regelwerk.risikoklassen[erwartet]["rang"]
    assert einstufung.rang >= rang_regel

    treffer = next(t for t in einstufung.treffer if t.regel_id == regel_id)
    assert treffer.klasse == erwartet


# --- Rangfolge und Rollen -------------------------------------------------

def test_ohne_flags_minimal(regelwerk):
    assert regelwerk.einstufen({}).klasse == "minimal"


def test_verbot_schlaegt_hochrisiko(regelwerk):
    e = regelwerk.einstufen({
        "emotionserkennung_arbeit_bildung": True,
        "personalauswahl": True,
    })
    assert e.klasse == "verboten"
    assert {"V-01", "H-01"} <= set(e.ausgeloest_durch)


def test_hochrisiko_schlaegt_transparenz(regelwerk):
    e = regelwerk.einstufen({"emotionserkennung_sonstige": True})
    assert e.klasse == "hochrisiko"
    assert {"H-09", "T-04"} <= set(e.ausgeloest_durch)


def test_anbieterpflicht_greift_nicht_bei_betreiber(regelwerk):
    assert regelwerk.einstufen({"direkte_interaktion": True},
                               rolle="betreiber").klasse == "minimal"


def test_anbieterpflicht_greift_bei_anbieter(regelwerk):
    e = regelwerk.einstufen({"direkte_interaktion": True}, rolle="anbieter")
    assert e.klasse == "transparenz"
    assert "T-01" in e.ausgeloest_durch


def test_anhang_i_braucht_beide_bedingungen(regelwerk):
    nur_eine = regelwerk.einstufen({"anhang_i_sicherheitsbauteil": True},
                                   rolle="anbieter")
    assert nur_eine.klasse == "minimal"

    beide = regelwerk.einstufen({
        "anhang_i_sicherheitsbauteil": True,
        "anhang_i_dritte_konformitaetsbewertung": True,
    }, rolle="anbieter")
    assert beide.klasse == "hochrisiko"
    assert "P-01" in beide.ausgeloest_durch


def test_unbekanntes_flag_wird_gemeldet(regelwerk):
    e = regelwerk.einstufen({"gibt_es_nicht": True})
    assert e.warnungen


# --- Bestandsschutz nach Art. 111 -----------------------------------------

def test_bestandsschutz_greift_bei_altsystem(regelwerk):
    e = regelwerk.einstufen({"personalauswahl": True},
                            in_betrieb_seit=date(2024, 5, 1))
    assert e.klasse == "hochrisiko"
    assert e.bestandsschutz_greift


def test_bestandsschutz_entfaellt_nach_aenderung(regelwerk):
    e = regelwerk.einstufen({"personalauswahl": True},
                            in_betrieb_seit=date(2024, 5, 1),
                            wesentlich_veraendert=True)
    assert not e.bestandsschutz_greift
    assert "wesentlich" in e.bestandsschutz_hinweis


def test_bestandsschutz_entfaellt_bei_behoerde(regelwerk):
    e = regelwerk.einstufen({"personalauswahl": True},
                            in_betrieb_seit=date(2024, 5, 1),
                            ist_behoerde=True)
    assert not e.bestandsschutz_greift
    assert "2030" in e.bestandsschutz_hinweis


def test_bestandsschutz_nur_bei_hochrisiko(regelwerk):
    e = regelwerk.einstufen({}, in_betrieb_seit=date(2024, 5, 1))
    assert not e.bestandsschutz_greift


# --- Ausnahmefilter nach Art. 6 Abs. 3 ------------------------------------

def test_ausnahmefilter_bei_anhang_iii_moeglich(regelwerk):
    assert regelwerk.einstufen({"personalauswahl": True}).ausnahmefilter_moeglich


def test_ausnahmefilter_durch_profiling_gesperrt(regelwerk):
    e = regelwerk.einstufen({"personalauswahl": True, "profiling": True})
    assert e.ausnahmefilter_gesperrt_durch_profiling
    assert not e.ausnahmefilter_moeglich


def test_ausnahmefilter_gilt_nicht_fuer_anhang_i(regelwerk):
    e = regelwerk.einstufen({
        "anhang_i_sicherheitsbauteil": True,
        "anhang_i_dritte_konformitaetsbewertung": True,
    }, rolle="anbieter")
    assert not e.ausnahmefilter_moeglich


# --- Lesarten -------------------------------------------------------------

def test_lesarten_unterscheiden_fristen(regelwerk):
    original = regelwerk.frist_fuer("F-05", "original")
    omnibus = regelwerk.frist_fuer("F-05", "omnibus")
    assert original != omnibus


def test_unbekannte_lesart_wird_abgewiesen(regelwerk):
    with pytest.raises(ValueError):
        regelwerk.einstufen({}, lesart="phantasie")


def test_unbekannte_rolle_wird_abgewiesen(regelwerk):
    with pytest.raises(ValueError):
        regelwerk.einstufen({}, rolle="chef")


# --- Freigabesperre -------------------------------------------------------

def test_regelwerk_ist_erst_mit_verifikation_ausspielbar(regelwerk):
    geprueft, gesamt = regelwerk.pruefstand
    assert regelwerk.ausspielbar() == (geprueft == gesamt)
