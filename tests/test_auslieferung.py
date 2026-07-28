"""
Prueft, was beim Ausliefern schiefgehen kann.

Kataster wirbt damit, dass keine Daten den Rechner verlassen. Eine einzige
externe Schriftreferenz wuerde das widerlegen - beim Seitenaufbau ginge eine
IP-Adresse an einen Fremdserver. Diese Pruefungen sind deshalb inhaltlich,
nicht kosmetisch.
"""

from __future__ import annotations

import re
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
CSS = WURZEL / "app" / "static" / "kataster.css"
SCHRIFTEN = WURZEL / "app" / "static" / "schriften"
TEMPLATES = WURZEL / "app" / "templates"


def test_css_hat_keine_externen_verweise():
    inhalt = CSS.read_text(encoding="utf-8")
    assert "http://" not in inhalt
    assert "https://" not in inhalt
    assert "//fonts." not in inhalt


def test_templates_laden_keine_externen_ressourcen():
    """Geprueft wird, was der Browser NACHLAEDT - nicht jede Erwaehnung von http.

    Ein Platzhaltertext wie placeholder="https://..." ist unschaedlich; ein
    src- oder href-Attribut auf eine fremde Adresse waere es nicht.
    """
    muster = re.compile(r'(?:src|href)\s*=\s*["\']https?://', re.I)
    treffer = []
    for datei in TEMPLATES.glob("*.html"):
        for nummer, zeile in enumerate(datei.read_text(encoding="utf-8").splitlines(), 1):
            if muster.search(zeile):
                treffer.append(f"{datei.name}:{nummer} {zeile.strip()[:70]}")
    assert not treffer, "Externe Ressourcen:\n" + "\n".join(treffer)


def test_jede_deklarierte_schrift_ist_eingebunden():
    """Der Fehler, der beim ersten Anlauf durchgerutscht ist."""
    inhalt = CSS.read_text(encoding="utf-8")
    deklariert = set()
    for zeile in inhalt.splitlines():
        if "--schrift-" in zeile or "font-family:" in zeile:
            deklariert |= set(re.findall(r'"([^"]+)"', zeile))

    eingebunden = set(re.findall(r'@font-face\s*\{[^}]*?font-family:\s*"([^"]+)"',
                                 inhalt, re.S))
    # Ausweichschriften des Systems muessen nicht eingebunden sein.
    system = {"Helvetica Neue", "Archivo Narrow", "Iowan Old Style",
              "SFMono-Regular", "Times New Roman"}
    fehlend = deklariert - eingebunden - system
    assert not fehlend, f"Deklariert, aber nicht eingebunden: {fehlend}"


def test_schriftdateien_liegen_vor():
    inhalt = CSS.read_text(encoding="utf-8")
    verwiesen = re.findall(r'url\("schriften/([^"]+)"\)', inhalt)
    assert verwiesen, "Keine Schriftdateien referenziert"
    fehlend = [name for name in verwiesen if not (SCHRIFTEN / name).exists()]
    assert not fehlend, f"Referenziert, aber nicht vorhanden: {fehlend}"


def test_lizenzen_liegen_bei():
    lizenzen = list(SCHRIFTEN.glob("LIZENZ-*.txt"))
    assert len(lizenzen) >= 3, "Zu jeder Schrift gehoert ihre Lizenz"
    for datei in lizenzen:
        assert datei.stat().st_size > 500


def test_datenbestand_wird_ignoriert():
    """Erfasste Systeme sind Unternehmensdaten und gehoeren nicht ins Repo."""
    gitignore = WURZEL / ".gitignore"
    assert gitignore.exists(), ".gitignore fehlt"
    inhalt = gitignore.read_text(encoding="utf-8")
    for muster in ("*.sqlite", "exporte/", "__pycache__/"):
        assert muster in inhalt, f"{muster} fehlt in .gitignore"
