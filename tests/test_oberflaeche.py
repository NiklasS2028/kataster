"""Prueft die Weboberflaeche vom Erfassen bis zum Nachweis."""

from __future__ import annotations

import re
from pathlib import Path

import pytest


def _wizard_durchklicken(klient, system_id, kontexte, ja=()):
    schritte = 0
    while schritte < 80:
        antwort = klient.get(f"/system/{system_id}/erfassen")
        if antwort.status_code == 302:
            break
        html = antwort.get_data(as_text=True)
        schluessel = re.search(r'name="schluessel" value="([^"]+)"', html).group(1)
        typ = re.search(r'name="typ" value="([^"]+)"', html).group(1)
        if typ == "mehrfachauswahl":
            daten = {"schluessel": schluessel, "typ": typ, "wert": list(kontexte)}
        elif typ == "datum":
            daten = {"schluessel": schluessel, "typ": typ, "wert": ""}
        else:
            daten = {"schluessel": schluessel, "typ": typ,
                     "wert": "ja" if schluessel in ja else "nein"}
        klient.post(f"/system/{system_id}/erfassen", data=daten)
        schritte += 1
    return schritte


@pytest.mark.parametrize("pfad", [
    "/", "/system/neu", "/organisation/", "/schatten/", "/nachweise",
])
def test_seiten_sind_erreichbar(klient, pfad):
    assert klient.get(pfad).status_code == 200


def test_unbekanntes_system_gibt_404(klient):
    assert klient.get("/system/999").status_code == 404


def test_system_ohne_namen_wird_abgewiesen(klient):
    assert klient.post("/system/neu", data={"name": "  "}).status_code == 400


def test_vollstaendiger_durchlauf(app, klient):
    klient.post("/organisation/", data={"name": "Musterbau GmbH",
                                        "ansprechpartner": "A. Weber"})
    klient.post("/system/neu", data={"name": "HR-Screening",
                                     "zweck": "Bewerbungen sichten",
                                     "abteilung": "Personal"})
    _wizard_durchklicken(klient, 1, ["personal"],
                         ja=["rolle:R-01", "flag:personalauswahl"])
    assert klient.post("/system/1/abschluss").status_code == 302

    with app.app_context():
        einstufung = app.datenbank().einstufung_aktuell(1)
    assert einstufung["klasse"] == "hochrisiko"

    seite = klient.get("/system/1").get_data(as_text=True)
    assert "Hochrisiko" in seite
    assert "H-01" in seite


def test_abgebrochener_wizard_hinterlaesst_nichts(app, klient):
    klient.post("/system/neu", data={"name": "Halbfertig"})
    klient.get("/system/1/erfassen")
    with app.app_context():
        assert app.datenbank().einstufung_aktuell(1) is None
        assert app.datenbank().flags_lesen(1) == {}


def test_bearbeiten_rechnet_neu(app, klient):
    klient.post("/system/neu", data={"name": "Altsystem"})
    _wizard_durchklicken(klient, 1, ["personal"],
                         ja=["rolle:R-01", "flag:personalauswahl"])
    klient.post("/system/1/abschluss")

    klient.post("/system/1/bearbeiten", data={
        "name": "Altsystem", "status": "freigegeben",
        "in_betrieb_seit": "2024-05-01",
    })
    with app.app_context():
        einstufung = app.datenbank().einstufung_aktuell(1)
    assert einstufung["klasse"] == "hochrisiko"
    assert einstufung["bestandsschutz_greift"] == 1


def test_loeschen_verlangt_den_namen(app, klient):
    klient.post("/system/neu", data={"name": "Wichtig"})
    klient.post("/system/1/loeschen", data={"bestaetigung": "falsch"})
    with app.app_context():
        assert app.datenbank().system_lesen(1) is not None
    klient.post("/system/1/loeschen", data={"bestaetigung": "Wichtig"})
    with app.app_context():
        assert app.datenbank().system_lesen(1) is None


def test_umfrage_buendelt_schreibweisen(klient):
    klient.post("/schatten/einlesen", data={"rohdaten":
        "ChatGPT;Texte;taeglich;Vertrieb\nchat gpt;Mails;selten;IT\n"
        "Chat-GPT;Notizen;selten;IT"})
    seite = klient.get("/schatten/").get_data(as_text=True)
    assert "auch genannt als" in seite
    treffer = re.findall(r'<td class="zahl">(\d+)</td>', seite)
    assert "3" in treffer


def test_umfrage_uebernimmt_nur_ausgewaehlte(app, klient):
    klient.post("/schatten/einlesen",
                data={"rohdaten": "DeepL;Uebersetzen;taeglich;Einkauf\n"
                                  "Midjourney;Bilder;selten;Marketing"})
    klient.post("/schatten/uebernehmen", data={"werkzeug": ["DeepL"]})
    with app.app_context():
        namen = [s["name"] for s in app.datenbank().systeme_auflisten()]
    assert namen == ["DeepL"]


def test_nachweise_werden_erzeugt(app, klient, tmp_path):
    klient.post("/organisation/", data={"name": "Musterbau GmbH"})
    klient.post("/system/neu", data={"name": "ChatGPT"})
    assert klient.post("/nachweise/erzeugen").status_code == 302
    assert klient.get("/exporte/dossier.html").status_code == 200
    with app.app_context():
        assert len(app.datenbank().nachweise_auflisten()) == 4


def test_zahlen_in_deutscher_schreibweise(app, klient):
    klient.post("/system/neu", data={"name": "Teuer", "kosten_monat_eur": "1234,50"})
    seite = klient.get("/").get_data(as_text=True)
    assert "1.234,50" in seite
    assert "1234.50" not in seite


def test_status_wird_lesbar_ausgegeben(app, klient):
    klient.post("/schatten/einlesen", data={"rohdaten": "DeepL;Uebersetzen;oft;IT"})
    klient.post("/schatten/uebernehmen", data={"werkzeug": ["DeepL"]})
    for pfad in ("/", "/schatten/"):
        seite = klient.get(pfad).get_data(as_text=True)
        assert "in_pruefung" not in seite, f"Rohwert sichtbar auf {pfad}"
        assert "in Prüfung" in seite


def test_groessenklasse_wird_gespeichert_und_vorbelegt(app, klient):
    klient.post("/organisation/", data={
        "name": "Mittelbau GmbH",
        "groessenklasse": "kleines_midcap",
        "hat_partner_oder_verbund": "on",
    })
    with app.app_context():
        org = app.datenbank().organisation_lesen()
    assert org["groessenklasse"] == "kleines_midcap"
    assert org["hat_partner_oder_verbund"] == 1
    seite = klient.get("/organisation/").get_data(as_text=True)
    assert 'value="kleines_midcap" selected' in seite


def test_unbekannte_groessenklasse_wird_verworfen(app, klient):
    """Nur die drei definierten Klassen duerfen in die Datenbank gelangen."""
    klient.post("/organisation/", data={"name": "X", "groessenklasse": "boese"})
    with app.app_context():
        assert app.datenbank().organisation_lesen()["groessenklasse"] is None


def test_pflichtenhinweis_nur_bei_bestandsschutz(app, klient):
    """Ohne Altsysteme waere der Hinweis irrefuehrend."""
    klient.post("/system/neu", data={"name": "Neusystem"})
    assert "Was der Bestandsschutz nicht abdeckt" not in klient.get("/").get_data(as_text=True)

    _wizard_durchklicken(klient, 1, ["personal"],
                         ja=["rolle:R-01", "flag:personalauswahl"])
    klient.post("/system/1/abschluss")
    klient.post("/system/1/bearbeiten", data={
        "name": "Neusystem", "status": "freigegeben", "in_betrieb_seit": "2024-05-01"})

    seite = klient.get("/").get_data(as_text=True)
    assert "Was der Bestandsschutz nicht abdeckt" in seite
    assert "Art. 5" in seite and "Art. 50" in seite
