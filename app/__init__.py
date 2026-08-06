"""
app/__init__.py - Flask-Factory fuer Kataster.

Laeuft lokal auf Port 8771. Keine Registrierung, kein Login, keine
Netzwerkfreigabe: Die erfassten Daten sind Compliance-Daten eines Unternehmens
und verlassen den Rechner nicht.
"""

from __future__ import annotations

import os
from pathlib import Path

from flask import Flask, g, render_template
from markupsafe import Markup

from .hinweise import als_html

PORT = 8771
WURZEL = Path(__file__).resolve().parent.parent
REGELWERK_STANDARD = WURZEL / "rules" / "ai-act_2026-07-23.yaml"
DATENBANK_STANDARD = WURZEL / "kataster.sqlite"


def erzeuge_app(testkonfiguration: dict | None = None) -> Flask:
    app = Flask(__name__, instance_relative_config=False)

    app.config.update(
        SECRET_KEY=os.environ.get("KATASTER_SECRET", os.urandom(24).hex()),
        REGELWERK_PFAD=str(REGELWERK_STANDARD),
        DATENBANK_PFAD=str(DATENBANK_STANDARD),
        SESSION_COOKIE_SAMESITE="Strict",
        SESSION_COOKIE_HTTPONLY=True,
        TEMPLATES_AUTO_RELOAD=True,
    )
    if testkonfiguration:
        app.config.update(testkonfiguration)

    from .regelwerk import Regelwerk
    from .modelle import Datenbank

    # Das Regelwerk aendert sich zur Laufzeit nicht - einmal laden genuegt.
    app.regelwerk = Regelwerk.laden(app.config["REGELWERK_PFAD"])

    def datenbank() -> Datenbank:
        if "datenbank" not in g:
            g.datenbank = Datenbank(app.config["DATENBANK_PFAD"])
        return g.datenbank

    app.datenbank = datenbank

    from .routen import inventar, organisation, schatten, wizard as wizard_routen

    app.register_blueprint(inventar.blueprint)
    app.register_blueprint(organisation.blueprint)
    app.register_blueprint(schatten.blueprint)
    app.register_blueprint(wizard_routen.blueprint)

    @app.template_filter("eur")
    def eur(wert) -> str:
        """Deutsche Schreibweise: Punkt als Tausender-, Komma als Dezimaltrenner."""
        if wert in (None, ""):
            return "\u2014"
        return f"{float(wert):,.2f}".replace(",", "\u00a0").replace(".", ",").replace("\u00a0", ".")

    STATUS_NAMEN = {
        "in_pruefung": "in Pr\u00fcfung",
        "freigegeben": "freigegeben",
        "geduldet": "geduldet",
        "untersagt": "untersagt",
    }

    @app.template_filter("statusname")
    def statusname(wert) -> str:
        return STATUS_NAMEN.get(wert, wert)

    @app.context_processor
    def standardwerte():
        rw = app.regelwerk
        geprueft, gesamt = rw.pruefstand
        return {
            "regelwerk": rw,
            "rechtsstand": rw.rechtsstand,
            "regelwerk_version": rw.version,
            "pruefstand": f"{geprueft}/{gesamt}",
            "regelwerk_ausspielbar": rw.ausspielbar(),
            "kein_rechtsrat": Markup(als_html()),
            "klassennamen": {
                s: d.get("bezeichnung", s) for s, d in rw.risikoklassen.items()
            },
            "statusnamen": STATUS_NAMEN,
        }

    @app.errorhandler(404)
    def nicht_gefunden(_):
        return render_template("fehler.html", code=404,
                               text="Diese Seite gibt es nicht."), 404

    @app.errorhandler(500)
    def serverfehler(_):
        return render_template("fehler.html", code=500,
                               text="Beim Verarbeiten ist etwas schiefgegangen. "
                                    "Die Eingaben wurden nicht gespeichert."), 500

    return app
