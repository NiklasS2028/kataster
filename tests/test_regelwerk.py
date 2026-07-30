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
    """G-06 und G-07 tragen keinen eigenen Regeltext, sondern zeigen auf Q-02.
    Nach dem Q-02-Folgecommit loesen beide Ziele auf."""
    q02 = next(q for q in regelwerk.querschnittspflichten if q["id"] == "Q-02")
    g06 = next(e for e in regelwerk.groessenregime["erleichterungen"] if e["id"] == "G-06")
    g07 = next(e for e in regelwerk.groessenregime["erleichterungen"] if e["id"] == "G-07")
    assert regelwerk.erleichterung_text(g06) == q02["kmu_regel"]
    assert regelwerk.erleichterung_text(g07) == q02["midcap_regel"]
    # Beide Dimensionen des Umfangsunterschieds muessen im Zieltext stehen, sonst
    # ist die Begruendung des Splits nur halb dokumentiert.
    assert "Dimensionen" in q02["kmu_regel"]
    assert "nur die Geldbussen nach Abs. 4 und Abs. 5" in q02["midcap_regel"]
    assert "nicht die nach Abs. 3" in q02["midcap_regel"]
    assert "Bezugsgroessen" in q02["midcap_regel"]


def test_zeiger_geschlossen_kein_offenes_ziel_mehr(regelwerk):
    """Nach dem Q-02-Folgecommit meldet die Validierung kein offenes Zeigerziel
    mehr und keinen Fehler im G-Block."""
    offene = [p for p in regelwerk.validieren()
              if p.ort.startswith("groessenregime/") and "noch nicht vorhanden" in p.text]
    assert not offene
    fehler = [p for p in regelwerk.validieren()
              if p.schwere == "fehler" and p.ort.startswith("groessenregime/")]
    assert not fehler


def test_zeiger_ohne_ziel_rendert_sichtbar_statt_leer(regelwerk):
    """Der Resolver darf ein offenes Zeigerziel nie leer rendern, sondern muss es
    sichtbar machen. Synthetisch geprueft, damit der Schutz unabhaengig vom
    aktuellen Datenstand bestehen bleibt."""
    fehlendes_feld = regelwerk.erleichterung_text(
        {"verweist_auf": "Q-02", "verweist_auf_feld": "gibt_es_nicht"})
    assert fehlendes_feld and "noch nicht vorhanden" in fehlendes_feld
    fehlendes_ziel = regelwerk.erleichterung_text(
        {"verweist_auf": "Q-99", "verweist_auf_feld": "egal"})
    assert fehlendes_ziel and "nicht gefunden" in fehlendes_ziel


def test_erleichterung_text_dict_fall_folgt_lesart(regelwerk):
    """Ein Dict-Fall liefert je Lesart den passenden Text."""
    g05 = next(e for e in regelwerk.groessenregime["erleichterungen"] if e["id"] == "G-05")
    original = regelwerk.erleichterung_text(g05, "original")
    omnibus = regelwerk.erleichterung_text(g05, "omnibus")
    assert original != omnibus
    assert "Midcap" in omnibus and "Midcap" not in original


def test_erleichterungen_ids_und_pruefstand(regelwerk):
    """Die sieben Eintraege sind vorhanden (G-02 entfaellt) und nach der Freigabe
    vom 2026-07-30 verifiziert."""
    eintraege = regelwerk.groessenregime["erleichterungen"]
    assert {e["id"] for e in eintraege} == {
        "G-01", "G-03", "G-04", "G-05", "G-06", "G-07", "G-08"}
    assert all(e["geprueft"] is True for e in eintraege)


def test_groessenregime_pruefstand_zaehlt_alle_einheiten(regelwerk):
    """Elf Verifikationseinheiten: Definitionen, drei Hinweisbloecke, sieben
    Erleichterungen. Nach der Freigabe vom 2026-07-30 alle verifiziert."""
    g_geprueft, g_gesamt = regelwerk.groessenregime_pruefstand
    assert g_gesamt == 11
    assert g_geprueft == 11


def test_geprueft_schalter_zerlegt(regelwerk):
    """Der frueher geteilte Schalter ist zerlegt: definitionen (je Eintrag),
    hinweis_zeitpunkt und hinweis_unterstuetzung tragen je ein eigenes geprueft,
    der Blockschalter groessenregime.geprueft ist entfallen."""
    g = regelwerk.groessenregime
    assert "geprueft" not in g  # kein Sammelschalter mehr auf Blockebene
    assert all("geprueft" in d for d in g["definitionen"])
    for schluessel in ("hinweis_zeitpunkt", "hinweis_unterstuetzung",
                       "hinweis_verhaeltnismaessigkeit"):
        assert isinstance(g[schluessel], dict)
        # Eigener Schalter je Einheit. Wert je nach Freigabestand, hier nur die
        # Struktur pruefen, damit der Test die Verifikationsrunden ueberlebt.
        assert isinstance(g[schluessel].get("geprueft"), bool)
    # Strukturfehler darf die Zerlegung nicht erzeugen.
    fehler = [p for p in regelwerk.validieren()
              if p.schwere == "fehler" and p.ort.startswith("groessenregime/")]
    assert not fehler


def test_anzeigbare_erleichterungen_nur_geprueft(regelwerk):
    """Kopplung der Anzeige an den G-Block-Pruefstand: die Anzeige gibt nur
    verifizierte Erleichterungen aus. Ein ungeprueft gebliebener Eintrag fiele
    heraus; nach der Freigabe vom 2026-07-30 sind alle strukturell passenden
    freigegeben, die Anzeige deckt daher den rohen Filter."""
    roh = regelwerk.erleichterungen_fuer("kmu", False, {"anbieter"}, {"hochrisiko"})
    anzeige = regelwerk.anzeigbare_erleichterungen(
        "kmu", False, {"anbieter"}, {"hochrisiko"})
    assert all(e.get("geprueft") is True for e in anzeige)
    assert {e["id"] for e in anzeige} <= {e["id"] for e in roh}
    assert {e["id"] for e in anzeige} == {e["id"] for e in roh}


def test_freigabestatus_weist_g_block_aus_ohne_zu_blockieren(regelwerk):
    """ausspielbar bleibt an den Regeln haengen; der G-Block wird getrennt
    ausgewiesen, nicht verschwiegen und nicht global blockierend."""
    status = regelwerk.freigabestatus()
    assert status["ausspielbar"] == regelwerk.ausspielbar()
    assert status["groessenregime_pruefstand"] == (11, 11)
    assert status["groessenregime_vollstaendig_geprueft"] is True
    # Die globale Ausspielbarkeit haengt nicht am G-Block.
    assert status["ausspielbar"] == (regelwerk.pruefstand[0] == regelwerk.pruefstand[1])


# -- Zeiger-Kopplung: Zielfeld-Pruefstand -----------------------------------

from pathlib import Path  # noqa: E402

_RW_PFAD = Path(__file__).resolve().parent.parent / "rules" / "ai-act_2026-07-23.yaml"


def _q02_feld(regelwerk, feld):
    q02 = next(q for q in regelwerk.querschnittspflichten if q["id"] == "Q-02")
    return q02.get(feld)


def test_q02_feldweise_flags_nachgezogen(regelwerk):
    """kmu_regel und midcap_regel tragen je einen eigenen, gesetzten Pruefstand
    (Nachzug der Freigabe vom 2026-07-30). Der entry-level Q-02-Schalter bleibt
    false, weil stufen weiter unverifiziert ist."""
    assert _q02_feld(regelwerk, "kmu_regel_geprueft") is True
    assert _q02_feld(regelwerk, "kmu_regel_geprueft_am") == "2026-07-30"
    assert _q02_feld(regelwerk, "kmu_regel_geprueft_von") == "Niklas Steinhauser"
    assert _q02_feld(regelwerk, "midcap_regel_geprueft") is True
    assert _q02_feld(regelwerk, "midcap_regel_geprueft_am") == "2026-07-30"
    assert _q02_feld(regelwerk, "midcap_regel_geprueft_von") == "Niklas Steinhauser"
    assert _q02_feld(regelwerk, "geprueft") is False


def test_zeigerziel_geprueft_bei_nicht_zeiger_immer_true(regelwerk):
    """Ein Eintrag ohne Zeiger hat kein Zielfeld und ist damit nie durch die
    Zielfeldpruefung blockiert."""
    g05 = next(e for e in regelwerk.groessenregime["erleichterungen"] if e["id"] == "G-05")
    assert regelwerk._zeigerziel_geprueft(g05) is True


def test_zeigerziel_geprueft_folgt_dem_zielfeld_flag(regelwerk):
    """G-06 zeigt auf Q-02.kmu_regel: die Pruefung folgt kmu_regel_geprueft."""
    g06 = next(e for e in regelwerk.groessenregime["erleichterungen"] if e["id"] == "G-06")
    assert regelwerk._zeigerziel_geprueft(g06) is True
    # Synthetisch: fehlendes Zielfeld-Flag ist nicht verifiziert.
    assert regelwerk._zeigerziel_geprueft(
        {"verweist_auf": "Q-02", "verweist_auf_feld": "gibt_es_nicht"}) is False
    assert regelwerk._zeigerziel_geprueft(
        {"verweist_auf": "Q-99", "verweist_auf_feld": "egal"}) is False


def test_anzeige_gate_greift_bei_unverifiziertem_zielfeld():
    """Kernbefund: ein verifizierter Zeiger darf keinen unverifizierten Zieltext
    ausspielen. Wird kmu_regel_geprueft zurueckgezogen, faellt G-06 aus der
    Anzeige, obwohl der G-Eintrag selbst geprueft bleibt und im rohen Filter
    weiter erscheint."""
    from app.regelwerk import Regelwerk
    rw = Regelwerk.laden(_RW_PFAD)
    q02 = next(q for q in rw.querschnittspflichten if q["id"] == "Q-02")
    q02["kmu_regel_geprueft"] = False

    roh_ids = {e["id"] for e in rw.erleichterungen_fuer(
        "kmu", False, {"anbieter"}, {"hochrisiko"})}
    anzeige_ids = {e["id"] for e in rw.anzeigbare_erleichterungen(
        "kmu", False, {"anbieter"}, {"hochrisiko"})}
    assert "G-06" in roh_ids            # im rohen Filter weiter vorhanden
    assert "G-06" not in anzeige_ids    # aus der Anzeige gefallen
    # Ein Nicht-Zeiger daneben bleibt unberuehrt.
    assert "G-05" in anzeige_ids


def test_validierung_meldet_fehlenden_zielfeld_pruefstand():
    """Fehlt am Zeiger-Zielfeld der eigene Pruefstand, meldet die Validierung
    einen Hinweis, nicht Fehler: der Zeiger fiele sonst still aus der Anzeige,
    die gefaehrlichste Fehlerklasse. Als Hinweis blockiert er die Ausspielung
    nicht."""
    from app.regelwerk import Regelwerk
    rw = Regelwerk.laden(_RW_PFAD)
    q02 = next(q for q in rw.querschnittspflichten if q["id"] == "Q-02")
    del q02["kmu_regel_geprueft"]
    probleme = rw.validieren()
    passend = [p for p in probleme
               if p.schwere == "hinweis" and "keinen eigenen Pruefstand" in p.text
               and "kmu_regel" in p.text]
    assert passend, "erwarteter Hinweis fehlt"
    # Kein Fehler, und die Ausspielung bleibt unberuehrt (Hinweis blockiert nicht).
    assert not [p for p in probleme if p.schwere == "fehler" and "kmu_regel" in p.text]
    assert rw.ausspielbar() is True
