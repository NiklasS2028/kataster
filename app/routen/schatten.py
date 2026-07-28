"""
routen/schatten.py - Erhebung und Uebernahme nicht erfasster KI-Nutzung.

Zweistufig: Der Import liest die Rueckmeldungen ein und zeigt sie zur Ansicht,
uebernommen wird erst nach Bestaetigung. Ein Fragebogen ist keine verlaessliche
Quelle - Schreibweisen weichen ab, Werkzeuge werden doppelt genannt, manches
ist gar kein KI-System. Das muss ein Mensch ansehen.
"""

from __future__ import annotations

import csv
import io
from datetime import datetime
from pathlib import Path

from flask import (Blueprint, current_app, redirect, render_template,
                   request, session, url_for)

blueprint = Blueprint("schatten", __name__, url_prefix="/schatten")

SPALTEN = ("werkzeug", "wofuer", "wie oft", "bereich")


def _db():
    return current_app.datenbank()


def _normieren(name: str) -> str:
    """Vergleichsform fuer Werkzeugnamen.

    Leerzeichen, Bindestriche und Punkte werden entfernt, damit ChatGPT,
    "Chat GPT" und "chat-gpt" als dasselbe gelten. Ziffern bleiben erhalten:
    "Claude" und "Claude 3" sind verschiedene Angaben und sollen es bleiben.
    """
    return "".join(z for z in name.lower() if z.isalnum())


def _lesen(rohtext: str) -> list[dict]:
    """Liest Semikolon- oder Komma-getrennte Rueckmeldungen ein."""
    if not rohtext.strip():
        return []
    trenner = ";" if rohtext.count(";") >= rohtext.count(",") else ","
    leser = csv.reader(io.StringIO(rohtext), delimiter=trenner)
    zeilen = [z for z in leser if any(feld.strip() for feld in z)]
    if not zeilen:
        return []

    # Kopfzeile erkennen, aber nicht voraussetzen.
    erste = [f.strip().lower() for f in zeilen[0]]
    if any(s in erste for s in SPALTEN):
        zeilen = zeilen[1:]

    meldungen = []
    for z in zeilen:
        felder = [f.strip() for f in z] + ["", "", "", ""]
        if not felder[0]:
            continue
        meldungen.append({
            "werkzeug": felder[0],
            "wofuer": felder[1],
            "haeufigkeit": felder[2],
            "bereich": felder[3],
        })
    return meldungen


def _buendeln(meldungen: list[dict], vorhandene: list[dict]) -> list[dict]:
    """Fasst gleiche Werkzeuge zusammen und markiert bereits erfasste."""
    bekannt = {_normieren(s["name"]): s for s in vorhandene}
    gebuendelt: dict[str, dict] = {}

    for m in meldungen:
        schluessel = _normieren(m["werkzeug"])
        eintrag = gebuendelt.setdefault(schluessel, {
            "werkzeug": m["werkzeug"],
            "nennungen": 0,
            "schreibweisen": {},
            "zwecke": [],
            "bereiche": [],
            "bereits_erfasst": schluessel in bekannt,
            "vorhandene_id": bekannt.get(schluessel, {}).get("id"),
        })
        eintrag["nennungen"] += 1
        eintrag["schreibweisen"][m["werkzeug"]] = (
            eintrag["schreibweisen"].get(m["werkzeug"], 0) + 1
        )
        if m["wofuer"] and m["wofuer"] not in eintrag["zwecke"]:
            eintrag["zwecke"].append(m["wofuer"])
        if m["bereich"] and m["bereich"] not in eintrag["bereiche"]:
            eintrag["bereiche"].append(m["bereich"])

    for eintrag in gebuendelt.values():
        # Die haeufigste Schreibweise gewinnt, bei Gleichstand die laengere -
        # "ChatGPT" ist aussagekraeftiger als "chatgpt".
        eintrag["werkzeug"] = max(
            eintrag["schreibweisen"].items(),
            key=lambda paar: (paar[1], len(paar[0])),
        )[0]
        eintrag["varianten"] = sorted(
            n for n in eintrag["schreibweisen"] if n != eintrag["werkzeug"]
        )
        del eintrag["schreibweisen"]

    return sorted(gebuendelt.values(),
                  key=lambda e: (e["bereits_erfasst"], -e["nennungen"]))


@blueprint.route("/")
def uebersicht():
    db = _db()
    gemeldet = db.systeme_auflisten(quelle="schatten_gemeldet")
    for s in gemeldet:
        s["einstufung"] = db.einstufung_aktuell(s["id"])
    return render_template(
        "schatten.html",
        gemeldet=gemeldet,
        vorschau=session.get("schatten_vorschau"),
        organisation=db.organisation_lesen(),
    )


@blueprint.route("/fragebogen", methods=["POST"])
def fragebogen():
    from ..export.umfrage import fragebogen_html, vorlage_csv
    from ..export import EXPORTORDNER

    db = _db()
    ordner = Path(current_app.config["DATENBANK_PFAD"]).parent / EXPORTORDNER
    ordner.mkdir(parents=True, exist_ok=True)
    zeitpunkt = datetime.now().replace(microsecond=0)

    (ordner / "umfrage-fragebogen.html").write_text(
        fragebogen_html(db.organisation_lesen(), zeitpunkt), encoding="utf-8")
    (ordner / "umfrage-vorlage.csv").write_text(vorlage_csv(), encoding="utf-8")
    return redirect(url_for("schatten.uebersicht", erzeugt=1))


@blueprint.route("/einlesen", methods=["POST"])
def einlesen():
    rohtext = request.form.get("rohdaten", "")
    datei = request.files.get("datei")
    if datei and datei.filename:
        rohtext = datei.read().decode("utf-8-sig", errors="replace")

    meldungen = _lesen(rohtext)
    vorhandene = _db().systeme_auflisten()
    session["schatten_vorschau"] = _buendeln(meldungen, vorhandene)
    return redirect(url_for("schatten.uebersicht"))


@blueprint.route("/uebernehmen", methods=["POST"])
def uebernehmen():
    db = _db()
    vorschau = session.get("schatten_vorschau") or []
    ausgewaehlt = set(request.form.getlist("werkzeug"))

    for eintrag in vorschau:
        if eintrag["werkzeug"] not in ausgewaehlt or eintrag["bereits_erfasst"]:
            continue
        zweck = "; ".join(eintrag["zwecke"][:3]) or None
        bereich = "; ".join(eintrag["bereiche"][:2]) or None
        notiz = f"Aus anonymer Umfrage, {eintrag['nennungen']} Nennung(en)."
        db.system_anlegen(
            name=eintrag["werkzeug"],
            zweck=zweck,
            abteilung=bereich,
            quelle="schatten_gemeldet",
            status="in_pruefung",
            notiz=notiz,
        )

    session.pop("schatten_vorschau", None)
    return redirect(url_for("schatten.uebersicht"))


@blueprint.route("/verwerfen", methods=["POST"])
def verwerfen():
    session.pop("schatten_vorschau", None)
    return redirect(url_for("schatten.uebersicht"))
