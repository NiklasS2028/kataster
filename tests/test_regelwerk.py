"""
Prueft das Regelwerk und die Einstufungslogik.

Der Kern ist test_jede_regel_loest_ihre_klasse_aus: Fuer jede einzelne Regel
wird geprueft, dass das zugehoerige Flag genau die erwartete Klasse erzeugt.
Faellt eine Regel aus dem Regelwerk oder aendert sich ihre Klasse, schlaegt
genau ein Test fehl - und zwar der mit dem passenden Namen.
"""

from __future__ import annotations

import re
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
    assert "P-02" in beide.ausgeloest_durch


def test_anhang_i_produkt_braucht_beide_bedingungen(regelwerk):
    nur_eine = regelwerk.einstufen({"anhang_i_produkt": True},
                                   rolle="anbieter")
    assert nur_eine.klasse == "minimal"

    beide = regelwerk.einstufen({
        "anhang_i_produkt": True,
        "anhang_i_dritte_konformitaetsbewertung": True,
    }, rolle="anbieter")
    assert beide.klasse == "hochrisiko"
    assert "P-01" in beide.ausgeloest_durch


def test_leistungsoptimierung_ist_kein_sicherheitsbauteil(regelwerk):
    # Art. 6 Abs. 1a: KI ausschliesslich zur Leistungsoptimierung in einer
    # Maschine ist kein Sicherheitsbauteil. Die Abgrenzung trifft der Wizard
    # ueber den Fragetext von P-02; hier wird nur abgesichert, dass ohne
    # gesetztes Flag kein Anhang-I-Treffer entsteht.
    e = regelwerk.einstufen({
        "anhang_i_dritte_konformitaetsbewertung": True,
    }, rolle="anbieter")
    assert e.klasse == "minimal"
    assert "P-01" not in e.ausgeloest_durch
    assert "P-02" not in e.ausgeloest_durch


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


def test_abschnitt_b_aendert_pflichtenregime_nicht_die_klasse(regelwerk):
    e = regelwerk.einstufen({
        "anhang_i_sicherheitsbauteil": True,
        "anhang_i_dritte_konformitaetsbewertung": True,
        "anhang_i_abschnitt_b": True,
    }, rolle="anbieter")
    assert e.klasse == "hochrisiko"
    assert e.abschnitt_b_greift
    assert "Art. 60a" in e.abschnitt_b_hinweis


def test_abschnitt_b_ohne_anhang_i_treffer_greift_nicht(regelwerk):
    e = regelwerk.einstufen({
        "personalauswahl": True,
        "anhang_i_abschnitt_b": True,
    }, rolle="anbieter")
    assert e.klasse == "hochrisiko"
    assert not e.abschnitt_b_greift


def test_abschnitt_b_setzt_bestandsschutz_aus(regelwerk):
    # Fuer Abschnitt B gilt Kapitel III nicht, Art. 111 Abs. 2 hat keinen
    # Anknuepfungspunkt. Statt still Bestandsschutz zu gewaehren, wird er
    # nicht berechnet.
    e = regelwerk.einstufen({
        "anhang_i_sicherheitsbauteil": True,
        "anhang_i_dritte_konformitaetsbewertung": True,
        "anhang_i_abschnitt_b": True,
    }, rolle="anbieter", in_betrieb_seit=date(2024, 5, 1))
    assert not e.bestandsschutz_greift
    assert e.abschnitt_b_hinweis is not None


def test_bestandsschutz_anhang_i_nutzt_spaeteren_stichtag(regelwerk):
    # Art. 111 Abs. 2 knuepft an den Geltungsbeginn des Kapitels III an.
    # Fuer Anhang I ist das F-06, nicht der allgemeine Geltungsbeginn F-03.
    e = regelwerk.einstufen({
        "anhang_i_produkt": True,
        "anhang_i_dritte_konformitaetsbewertung": True,
    }, rolle="anbieter", in_betrieb_seit=date(2027, 1, 1))
    assert e.klasse == "hochrisiko"
    assert e.bestandsschutz_greift


def test_bestandsschutz_anhang_iii_folgt_der_lesart(regelwerk):
    # In der Lesart omnibus verschiebt F-05 den Stichtag auf 2027-12-02.
    e = regelwerk.einstufen({"personalauswahl": True},
                            lesart="omnibus",
                            in_betrieb_seit=date(2027, 1, 1))
    assert e.klasse == "hochrisiko"
    assert e.bestandsschutz_greift


def test_bestandsschutz_bei_ueberschneidung_gilt_frueherer_stichtag(regelwerk):
    # Faellt ein System unter Anhang I und Anhang III, gilt F-05 (frueher)
    # und nicht F-06 - die konservative Wahl.
    e = regelwerk.einstufen({
        "personalauswahl": True,
        "anhang_i_produkt": True,
        "anhang_i_dritte_konformitaetsbewertung": True,
    }, rolle="anbieter", lesart="omnibus",
        in_betrieb_seit=date(2028, 1, 1))
    assert e.klasse == "hochrisiko"
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


def test_keine_zerbrochenen_woerter(regelwerk):
    """Faltungsartefakte aus der YAML aufspueren.

    Bei >- werden Zeilen mit einem Leerzeichen verbunden. Steht am Zeilenende
    ein Trennstrich, entsteht mitten im Wort eine Luecke: "unverhaeltnis-
    maessiger". Echte Ergaenzungsstriche im Deutschen stehen dagegen immer vor
    einer Konjunktion oder einem Artikel - "Aus- und Weiterbildung",
    "Lebens- oder Krankenversicherung". Danach wird unterschieden.
    """
    erlaubt = {"und", "oder", "bzw", "sowie", "beziehungsweise"}
    fehler = []
    for regel in regelwerk.regeln:
        for feld in ("frage", "hinweis", "ausnahmen", "massnahme"):
            text = regel.get(feld)
            if not text:
                continue
            for treffer in re.finditer(r"\w+-\s+(\w+)", text):
                if treffer.group(1).lower().rstrip(".,") not in erlaubt:
                    fehler.append(f"{regel['id']}.{feld}: {treffer.group()!r}")
    assert not fehler, "Zerbrochene Woerter:\n" + "\n".join(fehler)


# -- Groessenregime: KMU und kleine Midcaps ---------------------------------

def test_erleichterungen_ohne_groessenklasse_leer(regelwerk):
    """Ohne erfasste Groessenklasse gibt es nichts anzuzeigen."""
    assert regelwerk.erleichterungen_fuer(None, False, {"anbieter"}, {"hochrisiko"}) == []


def test_erleichterungen_art63_nur_kmu_ohne_verbund(regelwerk):
    """Art. 63 Abs. 1 (G-04) ist die Stelle, an der 'kleine Unternehmen bekommen
    Erleichterungen' falsch wird: Sie gilt nur KMU, nicht Midcaps, und nur ohne
    Partner- oder Verbundunternehmen. Das gilt in beiden Lesarten (im Ausgangs-
    recht sogar nur Kleinstunternehmen, im Werkzeug als Zuvielanzeige gefuehrt)."""
    def ids(klasse, verbund, lesart):
        return {e["id"] for e in regelwerk.erleichterungen_fuer(
            klasse, verbund, {"anbieter"}, {"hochrisiko"}, lesart=lesart)}

    for lesart in ("original", "omnibus"):
        # Midcap bekommt G-04 nicht, obwohl sonst dieselbe Anbieter-Hochrisiko-Lage.
        assert "G-04" not in ids("kleines_midcap", False, lesart)
        # KMU mit Partner/Verbund bekommt G-04 nicht.
        assert "G-04" not in ids("kmu", True, lesart)
        # KMU ohne Partner/Verbund bekommt G-04.
        assert "G-04" in ids("kmu", False, lesart)


def test_erleichterungen_art99_deckelung_getrennt_nach_absatz(regelwerk):
    """Art. 99 Deckelung: KMU ueber Abs. 6 (G-06, Ausgangsrecht, beide Lesarten),
    kleine Midcaps ueber Abs. 6a (G-07, omnibus-neu). Getrennte Eintraege, weil
    verschiedene Absaetze mit verschiedener Lesart-Verfuegbarkeit."""
    def ids(klasse, lesart):
        return {e["id"] for e in regelwerk.erleichterungen_fuer(
            klasse, False, set(), set(), lesart=lesart)}

    # KMU-Deckelung gilt in beiden Lesarten.
    assert "G-06" in ids("kmu", "original")
    assert "G-06" in ids("kmu", "omnibus")
    assert "G-06" not in ids("gross", "omnibus")
    # Midcap-Deckelung erst mit dem Omnibus.
    assert "G-07" not in ids("kleines_midcap", "original")
    assert "G-07" in ids("kleines_midcap", "omnibus")
    # G-06 ist nicht mehr die Midcap-Regel.
    assert "G-06" not in ids("kleines_midcap", "original")
    assert "G-06" not in ids("kleines_midcap", "omnibus")


def test_gilt_fuer_groesse_dict_folgt_der_lesart(regelwerk):
    """G-01 und G-05 erstrecken sich erst mit dem Omnibus auf kleine Midcaps.
    Unter original erhaelt ein Midcap sie nicht (Befund A: sonst bekaeme es eine
    Erleichterung, die im Ausgangsrecht nur KMU zusteht)."""
    def hat(eid, klasse, rollen, klassen, lesart):
        return eid in {e["id"] for e in regelwerk.erleichterungen_fuer(
            klasse, False, rollen, klassen, lesart=lesart)}

    assert not hat("G-01", "kleines_midcap", {"anbieter"}, {"hochrisiko"}, "original")
    assert hat("G-01", "kleines_midcap", {"anbieter"}, {"hochrisiko"}, "omnibus")
    assert not hat("G-05", "kleines_midcap", set(), set(), "original")
    assert hat("G-05", "kleines_midcap", set(), set(), "omnibus")
    # KMU dagegen in beiden Lesarten.
    assert hat("G-05", "kmu", set(), set(), "original")
    assert hat("G-05", "kmu", set(), set(), "omnibus")


def test_gilt_in_lesart_beschraenkt_omnibus_eintraege(regelwerk):
    """G-07 (Abs. 6a) und G-08 (Art. 57 Abs. 3a) sind omnibus-neu und duerfen
    unter original nicht erscheinen."""
    def ids(klasse, lesart):
        return {e["id"] for e in regelwerk.erleichterungen_fuer(
            klasse, False, set(), set(), lesart=lesart)}

    assert {"G-07", "G-08"}.isdisjoint(ids("kleines_midcap", "original"))
    assert "G-08" not in ids("kmu", "original")
    assert "G-08" in ids("kmu", "omnibus")
    assert "G-08" in ids("kleines_midcap", "omnibus")


def test_anbieter_erleichterung_laeuft_fuer_reinen_betreiber_leer(regelwerk):
    """Art. 11/63 treffen nur Anbieter von Hochrisiko-Systemen. Ein reiner
    Betreiber ohne Hochrisiko-System bekommt sie nicht, die von der Rolle
    unabhaengigen Erleichterungen (Art. 62, 99) aber schon."""
    treffer = {e["id"] for e in regelwerk.erleichterungen_fuer(
        "kmu", False, {"betreiber"}, {"minimal"})}
    assert {"G-01", "G-04"}.isdisjoint(treffer)
    assert {"G-03", "G-05", "G-06"} <= treffer


def test_g02_ist_kein_erleichterungseintrag_mehr(regelwerk):
    """Art. 17 Abs. 2 ist size-neutral und darf nicht als groessengebundene
    Erleichterung gefuehrt werden (sonst Vorenthaltung fuer grosse Anbieter)."""
    ids = {e["id"] for e in regelwerk.groessenregime["erleichterungen"]}
    assert "G-02" not in ids
    hinweis = regelwerk.groessenregime.get("hinweis_verhaeltnismaessigkeit")
    assert hinweis and "Art. 17 Abs. 2" in hinweis["text"]
    assert hinweis["fundstelle_original"] == "Art. 17 Abs. 2 KI-VO"


def test_zeiger_wird_gegen_q02_aufgeloest(regelwerk):
    """G-06 traegt keinen eigenen Regeltext, sondern zeigt auf Q-02.kmu_regel."""
    g06 = next(e for e in regelwerk.groessenregime["erleichterungen"] if e["id"] == "G-06")
    q02 = next(q for q in regelwerk.querschnittspflichten if q["id"] == "Q-02")
    assert regelwerk.erleichterung_text(g06) == q02["kmu_regel"]


def test_zeiger_ohne_ziel_rendert_sichtbar_statt_leer(regelwerk):
    """G-07 zeigt auf das noch fehlende Q-02.midcap_regel. Bis zum Folgecommit
    muss der Platzhalter sichtbar sein, nicht der leere String."""
    g07 = next(e for e in regelwerk.groessenregime["erleichterungen"] if e["id"] == "G-07")
    text = regelwerk.erleichterung_text(g07)
    assert text
    assert "midcap_regel" in text and "Folgecommit" in text
    # Und die Validierung meldet das offene Ziel als Hinweis, nicht als Fehler.
    hinweise = [p for p in regelwerk.validieren()
                if p.schwere == "hinweis" and "midcap_regel" in p.text]
    assert hinweise
    fehler = [p for p in regelwerk.validieren()
              if p.schwere == "fehler" and p.ort.startswith("groessenregime/")]
    assert not fehler


def test_erleichterung_text_dict_fall_folgt_lesart(regelwerk):
    """Ein Dict-Fall liefert je Lesart den passenden Text."""
    g05 = next(e for e in regelwerk.groessenregime["erleichterungen"] if e["id"] == "G-05")
    original = regelwerk.erleichterung_text(g05, "original")
    omnibus = regelwerk.erleichterung_text(g05, "omnibus")
    assert original != omnibus
    assert "Midcap" in omnibus and "Midcap" not in original


def test_erleichterungen_ids_und_pruefstand(regelwerk):
    """Die sieben Eintraege sind vorhanden (G-02 entfaellt) und alle noch
    unverifiziert."""
    eintraege = regelwerk.groessenregime["erleichterungen"]
    assert {e["id"] for e in eintraege} == {
        "G-01", "G-03", "G-04", "G-05", "G-06", "G-07", "G-08"}
    assert all(e["geprueft"] is False for e in eintraege)


def test_groessenregime_pruefstand_getrennt_von_regeln(regelwerk):
    """Der G-Block hat einen eigenen Pruefstand, hier noch nichts verifiziert."""
    g_geprueft, g_gesamt = regelwerk.groessenregime_pruefstand
    assert g_gesamt == 7
    assert g_geprueft == 0


def test_anzeigbare_erleichterungen_filtert_ungeprueft(regelwerk):
    """Kopplung der Anzeige an den G-Block-Pruefstand: ungeprueft = nicht sichtbar.

    Solange kein G-Eintrag verifiziert ist, liefert die Anzeige leer, obwohl der
    rohe Filter Treffer haette. So gelangt keine ungepruefte Rechtsformulierung
    ins Dossier, waehrend die uebrigen Exporte unberuehrt bleiben."""
    roh = regelwerk.erleichterungen_fuer("kmu", False, {"anbieter"}, {"hochrisiko"})
    anzeige = regelwerk.anzeigbare_erleichterungen(
        "kmu", False, {"anbieter"}, {"hochrisiko"})
    assert roh  # strukturell gibt es Treffer
    assert anzeige == []  # aber keiner ist verifiziert


def test_freigabestatus_weist_g_block_aus_ohne_zu_blockieren(regelwerk):
    """ausspielbar bleibt an den Regeln haengen; der G-Block wird getrennt
    ausgewiesen, nicht verschwiegen und nicht global blockierend."""
    status = regelwerk.freigabestatus()
    assert status["ausspielbar"] == regelwerk.ausspielbar()
    assert status["groessenregime_pruefstand"] == (0, 7)
    assert status["groessenregime_vollstaendig_geprueft"] is False
    # Die globale Ausspielbarkeit haengt nicht am G-Block.
    assert status["ausspielbar"] == (regelwerk.pruefstand[0] == regelwerk.pruefstand[1])
