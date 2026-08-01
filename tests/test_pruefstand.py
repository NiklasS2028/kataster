"""Integritaet aller Pruefvermerke im Regelwerk.

Prueft strukturell, dass jeder gesetzte Pruefvermerk vollstaendig und formal
korrekt ist - auf ALLEN Ebenen, nicht nur bei den Regeln. Ein rekursiver Walk
(geprueft_eintraege) erfasst jeden Block mit Pruefstand, auch spaeter ergaenzte,
sodass keiner durch die Maschen faellt. Das ist dieselbe Luecke, die beim
geteilten Schalter zweimal aufgetreten ist.
"""

from __future__ import annotations

import copy
import re

from app.regelwerk import geprueft_eintraege

ISO_DATUM = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _basis(schluessel: str) -> str:
    return schluessel[: -len("geprueft")]


def _maengel(daten) -> list[tuple[str, str, object]]:
    """Alle Formfehler an gesetzten Pruefvermerken: (pfad, feldart, wert)."""
    maengel: list[tuple[str, str, object]] = []
    for pfad, container, schluessel in geprueft_eintraege(daten):
        if container.get(schluessel) is not True:
            continue
        basis = _basis(schluessel)
        am = container.get(basis + "geprueft_am")
        von = container.get(basis + "geprueft_von")
        if not (isinstance(am, str) and ISO_DATUM.match(am)):
            maengel.append((pfad, "geprueft_am", am))
        if not (isinstance(von, str) and von.strip()):
            maengel.append((pfad, "geprueft_von", von))
    return maengel


def test_walk_erfasst_alle_ebenen(regelwerk):
    """Sicherung gegen einen stillen Ausfall des Walks: findet er nichts mehr,
    liefe der Integritaetstest leer durch und waere wertlos."""
    stellen = list(geprueft_eintraege(regelwerk._daten))
    assert len(stellen) >= 70, f"nur {len(stellen)} Pruefstellen gefunden"


def test_jeder_pruefvermerk_traegt_datum_und_pruefer(regelwerk):
    """Jedes geprueft: true auf jeder Ebene traegt geprueft_am (String im Format
    YYYY-MM-DD) und geprueft_von (nicht leer). Ein Datum ohne Anfuehrungszeichen
    laedt YAML als date-Objekt statt String und braeche spaeter beim Vergleich."""
    maengel = _maengel(regelwerk._daten)
    assert not maengel, "\n".join(f"{p}: {feld} = {wert!r}" for p, feld, wert in maengel)


def test_gegenprobe_fehlendes_datum(regelwerk):
    daten = copy.deepcopy(regelwerk._daten)
    for _, container, schluessel in geprueft_eintraege(daten):
        if container.get(schluessel) is True:
            container.pop(_basis(schluessel) + "geprueft_am", None)
            break
    assert any(feld == "geprueft_am" for _, feld, _ in _maengel(daten))


def test_gegenprobe_datum_als_date_objekt(regelwerk):
    """YAML laedt ein unquotiertes Datum als date-Objekt. Das muss auffallen,
    nicht durchrutschen."""
    from datetime import date
    daten = copy.deepcopy(regelwerk._daten)
    for _, container, schluessel in geprueft_eintraege(daten):
        if container.get(schluessel) is True:
            container[_basis(schluessel) + "geprueft_am"] = date(2026, 7, 30)
            break
    assert any(feld == "geprueft_am" for _, feld, _ in _maengel(daten))


def test_gegenprobe_datum_falsches_format(regelwerk):
    daten = copy.deepcopy(regelwerk._daten)
    for _, container, schluessel in geprueft_eintraege(daten):
        if container.get(schluessel) is True:
            container[_basis(schluessel) + "geprueft_am"] = "30.07.2026"
            break
    assert any(feld == "geprueft_am" for _, feld, _ in _maengel(daten))


def test_gegenprobe_leerer_pruefer(regelwerk):
    daten = copy.deepcopy(regelwerk._daten)
    for _, container, schluessel in geprueft_eintraege(daten):
        if container.get(schluessel) is True:
            container[_basis(schluessel) + "geprueft_von"] = "  "
            break
    assert any(feld == "geprueft_von" for _, feld, _ in _maengel(daten))
