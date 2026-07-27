"""
routen/inventar.py - Bestandsverzeichnis: Liste, Stammdaten, Detailblatt.
"""

from __future__ import annotations

from datetime import date

from pathlib import Path

from flask import (Blueprint, abort, current_app, redirect,
                   render_template, request, send_from_directory, url_for)

blueprint = Blueprint("inventar", __name__)


def _db():
    return current_app.datenbank()


def einstufung_neu_berechnen(system_id: int) -> dict:
    """Rechnet die Einstufung frisch und legt sie als neuen Datensatz ab."""
    rw = current_app.regelwerk
    db = _db()
    system = db.system_lesen(system_id)
    org = db.organisation_lesen()

    seit = None
    if system.get("in_betrieb_seit"):
        try:
            seit = date.fromisoformat(system["in_betrieb_seit"])
        except ValueError:
            seit = None

    einstufung = rw.einstufen(
        db.flags_lesen(system_id),
        rolle=system["rolle"],
        in_betrieb_seit=seit,
        wesentlich_veraendert=bool(system.get("wesentlich_veraendert_am")),
        ist_behoerde=bool(org.get("ist_behoerde")),
    )
    ergebnis = rw.als_dict(einstufung)
    db.einstufung_speichern(system_id, ergebnis)
    return ergebnis


@blueprint.route("/")
def liste():
    db = _db()
    systeme = db.systeme_auflisten()
    for s in systeme:
        s["einstufung"] = db.einstufung_aktuell(s["id"])
    return render_template(
        "liste.html",
        systeme=systeme,
        kennzahlen=db.kennzahlen(),
        organisation=db.organisation_lesen(),
    )


@blueprint.route("/system/neu", methods=["GET", "POST"])
def neu():
    if request.method == "POST":
        f = request.form
        name = f.get("name", "").strip()
        if not name:
            return render_template(
                "stammdaten.html", werte=f,
                fehler="Ohne Namen laesst sich das System spaeter nicht wiederfinden.",
            ), 400
        kosten = f.get("kosten_monat_eur", "").replace(",", ".").strip()
        try:
            kostenwert = float(kosten) if kosten else None
        except ValueError:
            return render_template(
                "stammdaten.html", werte=f,
                fehler="Die Monatskosten bitte als Zahl eintragen, etwa 24,90.",
            ), 400

        system_id = _db().system_anlegen(
            name=name,
            anbieter=f.get("anbieter", "").strip() or None,
            zweck=f.get("zweck", "").strip() or None,
            abteilung=f.get("abteilung", "").strip() or None,
            verantwortlich=f.get("verantwortlich", "").strip() or None,
            kosten_monat_eur=kostenwert,
            quelle=f.get("quelle", "offiziell"),
        )
        return redirect(url_for("wizard.frage", system_id=system_id))
    return render_template("stammdaten.html", werte={}, fehler=None)


@blueprint.route("/system/<int:system_id>")
def detail(system_id: int):
    db = _db()
    system = db.system_lesen(system_id)
    if not system:
        abort(404)

    aktuell = db.einstufung_aktuell(system_id)
    rw = current_app.regelwerk

    treffer = []
    if aktuell:
        for eintrag in aktuell["ergebnis"].get("treffer", []):
            regel = next((r for r in rw.regeln if r["id"] == eintrag["regel_id"]), None)
            if regel:
                treffer.append({**eintrag, "regel": regel})

    return render_template(
        "detail.html",
        system=system,
        einstufung=aktuell,
        treffer=treffer,
        flags=db.flags_lesen(system_id),
        historie=db.einstufung_historie(system_id),
        ausnahmen=db.ausnahmen_lesen(system_id),
    )


@blueprint.route("/system/<int:system_id>/neu-bewerten", methods=["POST"])
def neu_bewerten(system_id: int):
    if not _db().system_lesen(system_id):
        abort(404)
    einstufung_neu_berechnen(system_id)
    return redirect(url_for("inventar.detail", system_id=system_id))


@blueprint.route("/nachweise")
def nachweise():
    db = _db()
    return render_template(
        "nachweise.html",
        nachweise=db.nachweise_auflisten(),
        kennzahlen=db.kennzahlen(),
        organisation=db.organisation_lesen(),
    )


@blueprint.route("/nachweise/erzeugen", methods=["POST"])
def nachweise_erzeugen():
    from ..export import erzeuge_alle
    wurzel = Path(current_app.config["DATENBANK_PFAD"]).parent
    erzeuge_alle(_db(), current_app.regelwerk, wurzel)
    return redirect(url_for("inventar.nachweise"))


@blueprint.route("/exporte/<path:dateiname>")
def export_datei(dateiname: str):
    from ..export import EXPORTORDNER
    wurzel = Path(current_app.config["DATENBANK_PFAD"]).parent / EXPORTORDNER
    return send_from_directory(wurzel, dateiname)
