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

PORT = 8771
WURZEL = Path(__file__).resolve().parent.parent
REGELWERK_STANDARD = WURZEL / "rules" / "ai-act_2026-07-27.yaml"
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

    from .routen import inventar, wizard as wizard_routen

    app.register_blueprint(inventar.blueprint)
    app.register_blueprint(wizard_routen.blueprint)

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
            "klassennamen": {
                s: d.get("bezeichnung", s) for s, d in rw.risikoklassen.items()
            },
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
