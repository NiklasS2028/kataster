"""
export/schreiber.py - Erzeugt die Nachweise und traegt sie ins Register ein.
"""

from __future__ import annotations

import csv
import hashlib
import io
from datetime import datetime
from pathlib import Path

from ..hinweise import als_csv_zeilen
from .richtlinie import richtlinie_text
from .schulungsmatrix import matrix_text
from .dossier import dossier_html

EXPORTORDNER = "exporte"


def _hash(inhalt: bytes) -> str:
    return hashlib.sha256(inhalt).hexdigest()


def _schreiben(ordner: Path, name: str, inhalt: str) -> tuple[Path, str]:
    ordner.mkdir(parents=True, exist_ok=True)
    ziel = ordner / name
    rohdaten = inhalt.encode("utf-8")
    # Atomar schreiben: erst daneben, dann ersetzen. Ein abgebrochener Export
    # darf keine halbe Datei hinterlassen, die spaeter als Nachweis gilt.
    temp = ziel.with_suffix(ziel.suffix + ".tmp")
    temp.write_bytes(rohdaten)
    temp.replace(ziel)
    return ziel, _hash(rohdaten)


def _inventar_csv(systeme: list[dict], klassennamen: dict) -> str:
    puffer = io.StringIO()
    schreiber = csv.writer(puffer, delimiter=";", quoting=csv.QUOTE_MINIMAL)
    schreiber.writerow([
        "Lfd.", "System", "Anbieter", "Zweck", "Bereich", "Verantwortlich",
        "Rolle", "Einstufung", "Ausgeloest durch", "In Betrieb seit",
        "Bestandsschutz", "Kosten/Monat EUR", "Herkunft", "Status",
    ])
    for i, s in enumerate(systeme, start=1):
        e = s.get("einstufung")
        schreiber.writerow([
            f"{i:03d}", s["name"], s.get("anbieter") or "", s.get("zweck") or "",
            s.get("abteilung") or "", s.get("verantwortlich") or "", s["rolle"],
            klassennamen.get(e["klasse"], "") if e else "nicht erfasst",
            ", ".join(e["ausgeloest_durch"]) if e else "",
            s.get("in_betrieb_seit") or "",
            "ja" if e and e["bestandsschutz_greift"] else "nein",
            f"{s['kosten_monat_eur']:.2f}".replace(".", ",") if s.get("kosten_monat_eur") else "",
            "Umfrage" if s["quelle"] == "schatten_gemeldet" else "offiziell",
            s["status"],
        ])
    for zeile in als_csv_zeilen():
        schreiber.writerow(zeile)
    return puffer.getvalue()


def erzeuge_alle(db, regelwerk, wurzel: Path) -> list[dict]:
    """Erzeugt alle vier Nachweise. Gibt die Registereintraege zurueck."""
    ordner = Path(wurzel) / EXPORTORDNER
    organisation = db.organisation_lesen()
    systeme = db.systeme_auflisten()
    for s in systeme:
        s["einstufung"] = db.einstufung_aktuell(s["id"])
    kennzahlen = db.kennzahlen()
    klassennamen = {
        k: v.get("bezeichnung", k) for k, v in regelwerk.risikoklassen.items()
    }
    zeitpunkt = datetime.now().replace(microsecond=0)

    ausgaben = [
        ("inventar", "inventar.csv", _inventar_csv(systeme, klassennamen)),
        ("richtlinie", "ki-richtlinie.md",
         richtlinie_text(organisation, systeme, regelwerk, klassennamen, zeitpunkt)),
        ("schulung", "schulungsmatrix.md",
         matrix_text(organisation, systeme, regelwerk, zeitpunkt)),
        ("dossier", "dossier.html",
         dossier_html(organisation, systeme, kennzahlen, regelwerk,
                      klassennamen, zeitpunkt)),
    ]

    register = []
    for typ, name, inhalt in ausgaben:
        pfad, pruefsumme = _schreiben(ordner, name, inhalt)
        db.nachweis_erfassen(
            typ=typ,
            dateiname=name,
            regelwerk_version=regelwerk.version,
            rechtsstand=regelwerk.rechtsstand,
            hash_sha256=pruefsumme,
        )
        register.append({
            "typ": typ, "dateiname": name, "pfad": str(pfad),
            "hash": pruefsumme, "groesse": pfad.stat().st_size,
        })
    return register
