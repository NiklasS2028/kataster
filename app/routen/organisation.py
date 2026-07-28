"""
routen/organisation.py - Stammdaten des Unternehmens.

Zwei Angaben hier haben Rechtsfolgen und stehen deshalb nicht beim einzelnen
System: ist_behoerde hebelt den Bestandsschutz nach Art. 111 Abs. 2 aus, und
erbringt_oeff_dienste loest die Grundrechte-Folgenabschaetzung nach Art. 27 aus.
"""

from __future__ import annotations

from flask import (Blueprint, current_app, redirect,
                   render_template, request, url_for)

blueprint = Blueprint("organisation", __name__, url_prefix="/organisation")


@blueprint.route("/", methods=["GET", "POST"])
def bearbeiten():
    db = current_app.datenbank()

    if request.method == "POST":
        f = request.form
        beschaeftigte = f.get("beschaeftigte", "").strip()
        db.organisation_speichern(
            name=f.get("name", "").strip() or None,
            rechtsform=f.get("rechtsform", "").strip() or None,
            beschaeftigte=int(beschaeftigte) if beschaeftigte.isdigit() else None,
            ansprechpartner=f.get("ansprechpartner", "").strip() or None,
            ist_behoerde=1 if f.get("ist_behoerde") else 0,
            erbringt_oeff_dienste=1 if f.get("erbringt_oeff_dienste") else 0,
        )
        return redirect(url_for("organisation.bearbeiten", gespeichert=1))

    return render_template(
        "organisation.html",
        organisation=db.organisation_lesen(),
        gespeichert=request.args.get("gespeichert"),
    )
