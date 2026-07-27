"""
routen/wizard.py - Gefuehrte Erfassung eines Systems.

Antworten liegen bis zum Abschluss in der Session, nicht in der Datenbank.
Erst wenn der Fragebogen durch ist, werden Flags und Einstufung geschrieben -
ein abgebrochener Wizard hinterlaesst keine halbfertigen Nachweise.
"""

from __future__ import annotations

from flask import (Blueprint, abort, current_app, redirect,
                   render_template, request, session, url_for)

blueprint = Blueprint("wizard", __name__, url_prefix="/system")


def _db():
    return current_app.datenbank()


def _wizard():
    from ..wizard import Wizard
    org = _db().organisation_lesen()
    return Wizard(current_app.regelwerk, ist_behoerde=bool(org.get("ist_behoerde")))


def _schluessel(system_id: int) -> str:
    return f"wizard:{system_id}"


@blueprint.route("/<int:system_id>/erfassen", methods=["GET", "POST"])
def frage(system_id: int):
    db = _db()
    system = db.system_lesen(system_id)
    if not system:
        abort(404)

    w = _wizard()
    antworten = session.get(_schluessel(system_id), {})

    if request.method == "POST":
        feld = request.form["schluessel"]
        typ = request.form.get("typ")
        if typ == "mehrfachauswahl":
            antworten[feld] = request.form.getlist("wert")
        elif typ == "datum":
            antworten[feld] = request.form.get("wert") or None
        else:
            antworten[feld] = request.form.get("wert") == "ja"
        session[_schluessel(system_id)] = antworten
        return redirect(url_for("wizard.frage", system_id=system_id))

    naechste = w.naechste_frage(antworten)
    if naechste is None:
        return redirect(url_for("wizard.abschluss", system_id=system_id))

    beantwortet, gesamt = w.fortschritt(antworten)
    return render_template(
        "frage.html",
        system=system,
        frage=naechste,
        abschnitte=w.abschnitt_stand(antworten),
        beantwortet=beantwortet,
        gesamt=gesamt,
    )


@blueprint.route("/<int:system_id>/abschluss", methods=["GET", "POST"])
def abschluss(system_id: int):
    db = _db()
    system = db.system_lesen(system_id)
    if not system:
        abort(404)

    w = _wizard()
    antworten = session.get(_schluessel(system_id), {})
    ergebnis = w.auswerten(antworten)

    if request.method == "POST":
        for name, wert in ergebnis.flags.items():
            db.flag_setzen(system_id, name, wert, system.get("verantwortlich"))
        db.system_aktualisieren(
            system_id,
            rolle=ergebnis.rolle,
            in_betrieb_seit=(
                ergebnis.in_betrieb_seit.isoformat()
                if ergebnis.in_betrieb_seit else None
            ),
        )
        from .inventar import einstufung_neu_berechnen
        einstufung_neu_berechnen(system_id)
        session.pop(_schluessel(system_id), None)
        return redirect(url_for("inventar.detail", system_id=system_id))

    rw = current_app.regelwerk
    vorschau = None
    if not ergebnis.ausserhalb_anwendungsbereich:
        vorschau = rw.einstufen(
            ergebnis.flags,
            rolle=ergebnis.rolle,
            in_betrieb_seit=ergebnis.in_betrieb_seit,
            wesentlich_veraendert=ergebnis.wesentlich_veraendert,
        )

    return render_template(
        "abschluss.html", system=system, ergebnis=ergebnis, vorschau=vorschau
    )


@blueprint.route("/<int:system_id>/erfassen/zuruecksetzen", methods=["POST"])
def zuruecksetzen(system_id: int):
    session.pop(_schluessel(system_id), None)
    return redirect(url_for("wizard.frage", system_id=system_id))
