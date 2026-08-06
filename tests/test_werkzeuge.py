"""Die Werkzeuge unter tools/, soweit sie Dateien schreiben.

VERIFIKATION.md ist zur Haelfte erzeugt und zur Haelfte Handarbeit. Der
handgepflegte Teil (uebrige Pruefstaende, zweite Runde, die sechs Signale)
existiert nirgends sonst - kein Regelwerk, keine YAML, kein zweiter Ort, aus
dem er sich wiederherstellen liesse. Ein Werkzeug, das ihn bei einem
Routinelauf ueberschreibt, faellt beim ersten Mal auf und dann zu spaet.
"""

from __future__ import annotations

from tools import verifizieren

HANDGEPFLEGT = """

# Zweite Runde

Dieser Absatz steht nirgends sonst und laesst sich nicht neu erzeugen.
"""


def _arbeitsliste(tmp_path, monkeypatch, inhalt: str):
    ziel = tmp_path / "VERIFIKATION.md"
    ziel.write_text(inhalt, encoding="utf-8")
    monkeypatch.setattr(verifizieren, "ARBEITSLISTE", ziel)
    return ziel


def test_arbeitsliste_erhaelt_den_handgepflegten_teil(tmp_path, monkeypatch):
    ziel = _arbeitsliste(
        tmp_path, monkeypatch,
        "# Alter erzeugter Teil\n\nVeraltet.\n\n" + verifizieren.ENDMARKE + HANDGEPFLEGT,
    )

    assert verifizieren.arbeitsliste_schreiben() == 0

    neu = ziel.read_text(encoding="utf-8")
    assert neu.endswith(HANDGEPFLEGT)
    assert "Dieser Absatz steht nirgends sonst" in neu
    assert "# Verifikation der Fundstellen" in neu
    assert "Veraltet." not in neu
    assert neu.count(verifizieren.ENDMARKE) == 1


def test_arbeitsliste_schreibt_nicht_ohne_endmarke(tmp_path, monkeypatch):
    """Ohne Marke ist nicht erkennbar, wo das Erzeugte aufhoert. Dann lieber gar nichts."""
    vorher = "# Von Hand gepflegt\n\nOhne Trennmarke.\n"
    ziel = _arbeitsliste(tmp_path, monkeypatch, vorher)

    assert verifizieren.arbeitsliste_schreiben() == 1
    assert ziel.read_text(encoding="utf-8") == vorher


def test_arbeitsliste_legt_neu_an_und_setzt_die_marke(tmp_path, monkeypatch):
    ziel = tmp_path / "VERIFIKATION.md"
    monkeypatch.setattr(verifizieren, "ARBEITSLISTE", ziel)

    assert verifizieren.arbeitsliste_schreiben() == 0

    inhalt = ziel.read_text(encoding="utf-8")
    assert "# Verifikation der Fundstellen" in inhalt
    assert inhalt.rstrip().endswith(verifizieren.ENDMARKE)


def test_ausgelieferte_arbeitsliste_traegt_die_marke():
    """Die Datei im Repository muss die Marke tragen, sonst ist der Schutz nur Theorie."""
    inhalt = verifizieren.ARBEITSLISTE.read_text(encoding="utf-8")
    assert verifizieren.ENDMARKE in inhalt
    kopf, rest = inhalt.split(verifizieren.ENDMARKE, 1)
    assert "Verifikation der Fundstellen" in kopf
    assert "Zweite Runde" in rest
