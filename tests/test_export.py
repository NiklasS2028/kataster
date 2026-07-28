"""Prueft die Nachweise: Inhalt, Pruefsummen, Eigenstaendigkeit."""

from __future__ import annotations

import re
from pathlib import Path


def _bestand(datenbank, regelwerk):
    """Legt drei Systeme mit unterschiedlichen Einstufungen an."""
    datenbank.organisation_speichern(name="Musterbau GmbH",
                                     ansprechpartner="A. Weber")
    faelle = [
        ("ChatGPT Team", "Vertrieb", {}, "freigegeben"),
        ("HR-Screening", "Personal", {"personalauswahl": True}, "geduldet"),
        ("Bildgenerator", "Marketing", {"deepfake": True}, "freigegeben"),
    ]
    for name, bereich, flags, status in faelle:
        sid = datenbank.system_anlegen(name, abteilung=bereich, status=status,
                                       kosten_monat_eur=24.90)
        for flag, wert in flags.items():
            datenbank.flag_setzen(sid, flag, wert)
        datenbank.einstufung_speichern(
            sid, regelwerk.als_dict(regelwerk.einstufen(flags)))


def _erzeugen(datenbank, regelwerk, ordner: Path):
    from app.export import erzeuge_alle
    _bestand(datenbank, regelwerk)
    return erzeuge_alle(datenbank, regelwerk, ordner)


def test_alle_vier_nachweise_entstehen(datenbank, regelwerk, arbeitsordner):
    register = _erzeugen(datenbank, regelwerk, arbeitsordner)
    namen = {e["dateiname"] for e in register}
    assert namen == {"inventar.csv", "ki-richtlinie.md",
                     "schulungsmatrix.md", "dossier.html"}
    for eintrag in register:
        assert Path(eintrag["pfad"]).exists()
        assert eintrag["groesse"] > 0


def test_pruefsummen_werden_registriert(datenbank, regelwerk, arbeitsordner):
    register = _erzeugen(datenbank, regelwerk, arbeitsordner)
    eintraege = datenbank.nachweise_auflisten()
    assert len(eintraege) == 4
    for eintrag in eintraege:
        assert len(eintrag["hash_sha256"]) == 64
        assert eintrag["regelwerk_version"] == regelwerk.version
        assert eintrag["rechtsstand"] == regelwerk.rechtsstand


def test_pruefsumme_passt_zur_datei(datenbank, regelwerk, arbeitsordner):
    import hashlib
    register = _erzeugen(datenbank, regelwerk, arbeitsordner)
    for eintrag in register:
        gelesen = hashlib.sha256(Path(eintrag["pfad"]).read_bytes()).hexdigest()
        assert gelesen == eintrag["hash"]


def test_keine_temporaeren_reste(datenbank, regelwerk, arbeitsordner):
    _erzeugen(datenbank, regelwerk, arbeitsordner)
    reste = list((arbeitsordner / "exporte").glob("*.tmp"))
    assert not reste


def test_dossier_ist_eigenstaendig(datenbank, regelwerk, arbeitsordner):
    _erzeugen(datenbank, regelwerk, arbeitsordner)
    inhalt = (arbeitsordner / "exporte" / "dossier.html").read_text(encoding="utf-8")
    assert "http://" not in inhalt and "https://" not in inhalt
    assert "<style>" in inhalt
    assert "Kein Rechtsrat" in inhalt


def test_dossier_weist_entwurfsstand_aus(datenbank, regelwerk, arbeitsordner):
    _erzeugen(datenbank, regelwerk, arbeitsordner)
    inhalt = (arbeitsordner / "exporte" / "dossier.html").read_text(encoding="utf-8")
    if not regelwerk.ausspielbar():
        assert "Entwurfsstand" in inhalt
        assert "nicht als Nachweis" in inhalt


def test_richtlinie_fuehrt_freigegebene_systeme(datenbank, regelwerk, arbeitsordner):
    _erzeugen(datenbank, regelwerk, arbeitsordner)
    inhalt = (arbeitsordner / "exporte" / "ki-richtlinie.md").read_text(encoding="utf-8")
    assert "Musterbau GmbH" in inhalt
    assert "[Name des Unternehmens]" not in inhalt
    abschnitt = inhalt.split("## 2.")[1].split("##")[0]
    assert "ChatGPT Team" in abschnitt
    assert "HR-Screening" not in abschnitt


def test_richtlinie_trennt_geduldete_systeme(datenbank, regelwerk, arbeitsordner):
    _erzeugen(datenbank, regelwerk, arbeitsordner)
    inhalt = (arbeitsordner / "exporte" / "ki-richtlinie.md").read_text(encoding="utf-8")
    assert "Geduldet, aber nicht freigegeben" in inhalt


def test_richtlinie_laesst_freigabe_offen(datenbank, regelwerk, arbeitsordner):
    """Eine Richtlinie, die fertig aussieht, verfuehrt zum Nichtlesen."""
    _erzeugen(datenbank, regelwerk, arbeitsordner)
    inhalt = (arbeitsordner / "exporte" / "ki-richtlinie.md").read_text(encoding="utf-8")
    assert "Freigegeben durch: ___" in inhalt
    assert "tritt in Kraft am: ___" in inhalt


def test_schulungsmatrix_ordnet_bereiche_zu(datenbank, regelwerk, arbeitsordner):
    _erzeugen(datenbank, regelwerk, arbeitsordner)
    inhalt = (arbeitsordner / "exporte" / "schulungsmatrix.md").read_text(encoding="utf-8")
    assert "### Personal" in inhalt
    assert "### Marketing" in inhalt
    assert "S-04" in inhalt


def test_schulungsmatrix_zeigt_massnahmen_statt_niveau(datenbank, regelwerk,
                                                       arbeitsordner):
    """Art. 4 i. d. F. VO (EU) 2026/1744: dokumentiert werden ergriffene
    Massnahmen, kein garantiertes Kompetenzniveau (Art. 4 Abs. 1 Satz 2).

    Strukturell: Die Massnahmen-Tabelle traegt die geforderten Spalten, und
    keine Kopfzeile behauptet ein Niveau-Feld. Die inhaltliche Klarstellung
    prueft test_schulungsmatrix_belegt_klarstellung_zu_niveau."""
    _erzeugen(datenbank, regelwerk, arbeitsordner)
    inhalt = (arbeitsordner / "exporte" / "schulungsmatrix.md").read_text(
        encoding="utf-8")

    # Die Massnahmen-Tabelle traegt die geforderten Spalten. Geprueft werden die
    # getrimmten Zellen ihrer Kopfzeile, nicht die Spaltenbreite. "Zuschnitt"
    # muss in dieser Kopfzeile stehen, nicht irgendwo im Dokument.
    assert "## Ergriffene Maßnahmen" in inhalt
    abschnitt = inhalt.split("## Ergriffene Maßnahmen", 1)[1]
    tabellenzeilen = [z for z in abschnitt.splitlines()
                      if z.lstrip().startswith("|")]
    assert tabellenzeilen, "Massnahmen-Tabelle fehlt im Export"
    zellen = [c.strip() for c in tabellenzeilen[0].strip().strip("|").split("|")]
    assert "Maßnahme" in zellen
    assert "Datum" in zellen
    assert "Teilnehmerkreis" in zellen
    assert any(c.startswith("Zuschnitt") for c in zellen), (
        f"Spalte Zuschnitt fehlt in der Kopfzeile: {zellen}")

    # Keine Tabellenueberschrift behauptet ein Niveau-Feld. Geprueft werden die
    # Markdown-Kopfzeilen (beginnen mit "|", ohne die Trennzeile).
    kopfzeilen = [z for z in inhalt.splitlines()
                  if z.lstrip().startswith("|") and "---" not in z]
    for zeile in kopfzeilen:
        assert "niveau" not in zeile.lower()


def test_schulungsmatrix_belegt_klarstellung_zu_niveau(datenbank, regelwerk,
                                                       arbeitsordner):
    """Der Export gibt die Klarstellung aus Art. 4 Abs. 1 Satz 2 wieder: fuer
    keine Person muss ein bestimmtes Kompetenzniveau garantiert werden. Geprueft
    wird der Verweis auf die Norm, nicht eine bestimmte Formulierung. Damit
    bleibt jede fachlich korrekte Umformulierung der Klarstellung zulaessig,
    solange die tragende Norm genannt ist."""
    _erzeugen(datenbank, regelwerk, arbeitsordner)
    inhalt = (arbeitsordner / "exporte" / "schulungsmatrix.md").read_text(
        encoding="utf-8")
    assert "Art. 4 Abs. 1 Satz 2" in inhalt, (
        "Klarstellung aus Art. 4 Abs. 1 Satz 2 fehlt im Export: kein Verweis "
        "auf die tragende Norm gefunden")


def test_csv_enthaelt_alle_systeme(datenbank, regelwerk, arbeitsordner):
    _erzeugen(datenbank, regelwerk, arbeitsordner)
    zeilen = (arbeitsordner / "exporte" / "inventar.csv").read_text(
        encoding="utf-8").strip().splitlines()
    assert len(zeilen) == 4
    assert zeilen[0].startswith("Lfd.;System;")
    assert "24,90" in zeilen[1]


def test_fragebogen_sagt_folgenlosigkeit_zu(datenbank, regelwerk, arbeitsordner):
    """Ohne diese Zusage antwortet niemand ehrlich - sie ist funktional."""
    from app.export.umfrage import fragebogen_html
    from datetime import datetime
    inhalt = fragebogen_html({"name": "Musterbau GmbH"}, datetime.now())
    assert "anonym" in inhalt
    assert "folgenlos" in inhalt
    assert "http" not in inhalt


def test_dossier_meldet_abweichende_regelwerksfassung(datenbank, regelwerk, arbeitsordner):
    """Ein Dossier, dessen Kopf 1.0.0 sagt und dessen Nachweise 0.3.0 sagen,
    liest sich als Fehler - auch wenn es korrekt historisiert ist."""
    import sqlite3
    _bestand(datenbank, regelwerk)
    with datenbank.verbindung() as con:
        con.execute("UPDATE einstufung SET regelwerk_version = 'alt-0.0.1'")

    from app.export import erzeuge_alle
    erzeuge_alle(datenbank, regelwerk, arbeitsordner)
    inhalt = (arbeitsordner / "exporte" / "dossier.html").read_text(encoding="utf-8")
    assert "Abweichende Regelwerksfassung" in inhalt
    assert "aelter als der Kopfstand" in inhalt


def test_dossier_ohne_abweichung_ohne_warnung(datenbank, regelwerk, arbeitsordner):
    _erzeugen(datenbank, regelwerk, arbeitsordner)
    inhalt = (arbeitsordner / "exporte" / "dossier.html").read_text(encoding="utf-8")
    assert "Abweichende Regelwerksfassung" not in inhalt


def test_dossier_nutzt_deutsche_zahlen(datenbank, regelwerk, arbeitsordner):
    _erzeugen(datenbank, regelwerk, arbeitsordner)
    inhalt = (arbeitsordner / "exporte" / "dossier.html").read_text(encoding="utf-8")
    assert "74,70" in inhalt      # 3 x 24,90 monatlich
    assert "74.70" not in inhalt
