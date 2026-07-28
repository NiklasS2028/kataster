"""
regelwerk.py - Laden, Validieren und Auswerten des Regelwerks.

Dieses Modul enthaelt bewusst KEIN Rechtswissen. Alle Paragraphen, Fragen,
Fundstellen und Klassen stehen in der YAML unter rules/. Aendert sich die
Rechtslage, aendert sich die YAML - nicht dieser Code.

Die Einstufung ist rein regelbasiert und deterministisch. Kein Modellaufruf,
keine Heuristik. Das ist Voraussetzung dafuer, dass ein Nachweis-Dossier
ueberhaupt belastbar sein kann.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import yaml

LESARTEN = ("original", "omnibus")
ROLLEN = ("betreiber", "anbieter", "beides")


# ---------------------------------------------------------------------------
# Datencontainer
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Treffer:
    """Eine Regel, die auf ein System zutrifft."""

    regel_id: str
    klasse: str
    rang: int
    fundstelle: str
    frage: str
    massnahme: str | None = None
    ausnahmen: str | None = None
    hinweis: str | None = None
    frist: str | None = None
    geprueft: bool = False


@dataclass
class Einstufung:
    """Ergebnis einer Auswertung. Wird historisiert, nie ueberschrieben."""

    klasse: str
    rang: int
    treffer: list[Treffer] = field(default_factory=list)
    lesart: str = "original"
    rolle: str = "betreiber"
    regelwerk_version: str = ""
    rechtsstand: str = ""
    berechnet_am: str = ""
    bestandsschutz_greift: bool = False
    bestandsschutz_hinweis: str | None = None
    ausnahmefilter_moeglich: bool = False
    ausnahmefilter_gesperrt_durch_profiling: bool = False
    warnungen: list[str] = field(default_factory=list)

    @property
    def ausgeloest_durch(self) -> list[str]:
        return [t.regel_id for t in self.treffer]


@dataclass
class Problem:
    """Ein bei der Validierung gefundener Mangel im Regelwerk."""

    schwere: str  # "fehler" | "warnung" | "hinweis"
    ort: str
    text: str


# ---------------------------------------------------------------------------
# Regelwerk
# ---------------------------------------------------------------------------


class Regelwerk:
    def __init__(self, daten: dict[str, Any], quelldatei: Path | None = None):
        self._daten = daten
        self.quelldatei = quelldatei
        self.meta: dict[str, Any] = daten.get("meta", {})
        self.lesarten: dict[str, Any] = daten.get("lesarten", {})
        self.fristen: list[dict] = daten.get("fristen", [])
        self.regeln: list[dict] = daten.get("regeln", [])
        self.risikoklassen: dict[str, Any] = daten.get("risikoklassen", {})
        self.querschnittspflichten: list[dict] = daten.get("querschnittspflichten", [])
        self.rollenbestimmung: dict[str, Any] = daten.get("rollenbestimmung", {})
        self.ausnahmefilter: dict[str, Any] = daten.get("ausnahmefilter_anhang_iii", {})
        self.bestandsschutz: list[dict] = daten.get("bestandsschutz", [])
        self.anwendungsbereich: list[dict] = daten.get("anwendungsbereich_ausnahmen", [])
        self.einsatzkontexte: dict[str, Any] = daten.get("einsatzkontexte", {})
        self.schulungsbausteine: list[dict] = daten.get("schulungsbausteine", [])
        self.quellen: list[dict] = daten.get("quellen", [])

    # -- Laden ---------------------------------------------------------------

    @classmethod
    def laden(cls, pfad: str | Path) -> "Regelwerk":
        pfad = Path(pfad)
        with open(pfad, "r", encoding="utf-8") as f:
            daten = yaml.safe_load(f)
        if not isinstance(daten, dict):
            raise ValueError(f"{pfad}: Regelwerk ist kein YAML-Mapping.")
        return cls(daten, quelldatei=pfad)

    # -- Kennzahlen ----------------------------------------------------------

    @property
    def version(self) -> str:
        return self.meta.get("regelwerk_version", "unbekannt")

    @property
    def rechtsstand(self) -> str:
        return self.meta.get("rechtsstand", "unbekannt")

    @property
    def pruefstand(self) -> tuple[int, int]:
        """(geprueft, gesamt) ueber alle Regeln - fuer README und UI."""
        gesamt = len(self.regeln)
        geprueft = sum(1 for r in self.regeln if r.get("geprueft") is True)
        return geprueft, gesamt

    def hash(self) -> str:
        """SHA-256 ueber die Quelldatei. Kommt in jedes Nachweis-Dossier."""
        if not self.quelldatei:
            return ""
        return hashlib.sha256(self.quelldatei.read_bytes()).hexdigest()

    def flag_namen(self) -> list[str]:
        namen = []
        for r in self.regeln:
            namen.append(r["trifft_zu_wenn"])
            zusatz = r.get("zusatzbedingung")
            if zusatz:
                namen.append(zusatz["trifft_zu_wenn"])
        # Das Sperrkriterium des Ausnahmefilters ist ein Flag ohne eigene Regel.
        sperr_flag = self.ausnahmefilter.get("gilt_nicht_bei")
        if sperr_flag:
            namen.append(sperr_flag)
        return sorted(set(namen))

    def frist_fuer(self, frist_id: str | None, lesart: str) -> str | None:
        if not frist_id:
            return None
        for f in self.fristen:
            if f.get("id") == frist_id:
                return f.get(lesart)
        return None

    # -- Validierung ---------------------------------------------------------

    def validieren(self) -> list[Problem]:
        probleme: list[Problem] = []

        gesehene_ids: set[str] = set()
        for r in self.regeln:
            ort = f"regeln/{r.get('id', '???')}"

            for pflicht in ("id", "frage", "trifft_zu_wenn", "klasse", "fundstelle"):
                if not r.get(pflicht):
                    probleme.append(Problem("fehler", ort, f"Feld '{pflicht}' fehlt."))

            rid = r.get("id")
            if rid in gesehene_ids:
                probleme.append(Problem("fehler", ort, "Doppelte Regel-ID."))
            gesehene_ids.add(rid)

            klasse = r.get("klasse")
            if klasse and klasse not in self.risikoklassen:
                probleme.append(
                    Problem("fehler", ort, f"Unbekannte Risikoklasse '{klasse}'.")
                )

            fr = r.get("frist_ref")
            if fr and not any(f.get("id") == fr for f in self.fristen):
                probleme.append(Problem("fehler", ort, f"Frist '{fr}' existiert nicht."))

            for rolle in r.get("nur_bei_rolle", []) or []:
                if rolle not in ROLLEN:
                    probleme.append(Problem("fehler", ort, f"Unbekannte Rolle '{rolle}'."))

            if r.get("geprueft") is not True:
                probleme.append(
                    Problem("warnung", ort, "Fundstelle noch nicht verifiziert.")
                )

        if self.lesarten.get("omnibus", {}).get("amtsblatt") in (None, ""):
            probleme.append(
                Problem(
                    "hinweis",
                    "lesarten/omnibus",
                    "Amtsblatt-Fundstelle fehlt. Omnibus-Lesart gilt als unbestaetigt.",
                )
            )

        return probleme

    def ausspielbar(self) -> bool:
        """True nur, wenn kein Fehler und keine ungeprueften Regeln vorliegen."""
        return not any(p.schwere in ("fehler", "warnung") for p in self.validieren())

    # -- Einstufung ----------------------------------------------------------

    def _regel_greift(self, regel: dict, flags: dict[str, bool], rolle: str) -> bool:
        rollen = regel.get("nur_bei_rolle")
        if rollen:
            passend = rolle in rollen or (rolle == "beides" and set(rollen) & set(ROLLEN))
            if not passend:
                return False

        if not flags.get(regel["trifft_zu_wenn"], False):
            return False

        zusatz = regel.get("zusatzbedingung")
        if zusatz and not flags.get(zusatz["trifft_zu_wenn"], False):
            return False

        return True

    def einstufen(
        self,
        flags: dict[str, bool],
        rolle: str = "betreiber",
        lesart: str = "original",
        in_betrieb_seit: date | None = None,
        wesentlich_veraendert: bool = False,
        ist_behoerde: bool = False,
    ) -> Einstufung:
        if lesart not in LESARTEN:
            raise ValueError(f"Unbekannte Lesart: {lesart}")
        if rolle not in ROLLEN:
            raise ValueError(f"Unbekannte Rolle: {rolle}")

        warnungen: list[str] = []
        unbekannt = set(flags) - set(self.flag_namen())
        if unbekannt:
            warnungen.append(
                "Flags ohne zugehoerige Regel: " + ", ".join(sorted(unbekannt))
            )

        treffer: list[Treffer] = []
        for regel in self.regeln:
            if not self._regel_greift(regel, flags, rolle):
                continue
            klasse = regel["klasse"]
            treffer.append(
                Treffer(
                    regel_id=regel["id"],
                    klasse=klasse,
                    rang=self.risikoklassen[klasse]["rang"],
                    fundstelle=regel["fundstelle"],
                    frage=regel["frage"],
                    massnahme=regel.get("massnahme"),
                    ausnahmen=regel.get("ausnahmen"),
                    hinweis=regel.get("hinweis"),
                    frist=self.frist_fuer(regel.get("frist_ref"), lesart),
                    geprueft=regel.get("geprueft") is True,
                )
            )

        if treffer:
            hoechster = max(treffer, key=lambda t: t.rang)
            klasse, rang = hoechster.klasse, hoechster.rang
        else:
            klasse, rang = "minimal", self.risikoklassen["minimal"]["rang"]

        treffer.sort(key=lambda t: (-t.rang, t.regel_id))

        einstufung = Einstufung(
            klasse=klasse,
            rang=rang,
            treffer=treffer,
            lesart=lesart,
            rolle=rolle,
            regelwerk_version=self.version,
            rechtsstand=self.rechtsstand,
            berechnet_am=date.today().isoformat(),
            warnungen=warnungen,
        )

        self._bestandsschutz_pruefen(
            einstufung, in_betrieb_seit, wesentlich_veraendert, ist_behoerde, lesart
        )
        self._ausnahmefilter_pruefen(einstufung, flags)

        return einstufung

    # -- Nebenpruefungen -----------------------------------------------------

    def _bestandsschutz_pruefen(
        self,
        einstufung: Einstufung,
        in_betrieb_seit: date | None,
        wesentlich_veraendert: bool,
        ist_behoerde: bool,
        lesart: str,
    ) -> None:
        if einstufung.klasse != "hochrisiko" or in_betrieb_seit is None:
            return

        # Art. 111 Abs. 2 knuepft an den Geltungsbeginn des Kapitels III an,
        # nicht an den allgemeinen Geltungsbeginn. Der ist seit Art. 113
        # Abs. 3 lit. c gespalten: F-05 fuer Anhang III, F-06 fuer Anhang I.
        # Bei Ueberschneidung gilt der fruehere Termin (F-05) - die
        # konservative Wahl, weil sie weniger Bestandsschutz gewaehrt.
        anhang_i = any(t.regel_id in ("P-01", "P-02") for t in einstufung.treffer)
        anhang_iii = any(
            t.regel_id not in ("P-01", "P-02") for t in einstufung.treffer
        )
        frist_id = "F-05" if anhang_iii or not anhang_i else "F-06"

        stichtag_str = self.frist_fuer(frist_id, lesart)
        if not stichtag_str:
            return
        stichtag = date.fromisoformat(stichtag_str)

        if in_betrieb_seit >= stichtag:
            return

        if ist_behoerde:
            einstufung.bestandsschutz_hinweis = (
                "System vor dem Stichtag in Betrieb, wird aber von einer Behoerde "
                "verwendet. Kein Bestandsschutz: Umsetzung bis 2030-08-02 "
                "erforderlich (Art. 111 Abs. 2 KI-VO)."
            )
            return

        if wesentlich_veraendert:
            einstufung.bestandsschutz_hinweis = (
                "System vor dem Stichtag in Betrieb, seitdem aber wesentlich "
                "veraendert. Bestandsschutz entfaellt (Art. 111 Abs. 2 KI-VO)."
            )
            return

        einstufung.bestandsschutz_greift = True
        einstufung.bestandsschutz_hinweis = (
            "System wurde vor dem Stichtag in Betrieb genommen und seitdem nicht "
            "wesentlich veraendert. Die Hochrisiko-Pflichten greifen nach "
            "Art. 111 Abs. 2 KI-VO derzeit nicht. Bei jeder wesentlichen "
            "Veraenderung neu bewerten."
        )

    def _ausnahmefilter_pruefen(
        self, einstufung: Einstufung, flags: dict[str, bool]
    ) -> None:
        if einstufung.klasse != "hochrisiko":
            return

        # Der Filter des Art. 6 Abs. 3 gilt nur fuer Anhang III, nicht fuer
        # den Anhang-I-Pfad. Greift P-01 oder P-02, ist er ausgeschlossen.
        if any(t.regel_id in ("P-01", "P-02") for t in einstufung.treffer):
            return

        sperr_flag = self.ausnahmefilter.get("gilt_nicht_bei")
        if sperr_flag and flags.get(sperr_flag, False):
            einstufung.ausnahmefilter_gesperrt_durch_profiling = True
            return

        einstufung.ausnahmefilter_moeglich = True

    # -- Ausgabe -------------------------------------------------------------

    def klassentext(self, klasse: str) -> str:
        eintrag = self.risikoklassen.get(klasse, {})
        return eintrag.get("aussage", "")

    def als_dict(self, einstufung: Einstufung) -> dict[str, Any]:
        """Serialisierbare Form fuer Datenbank und Export."""
        return {
            "klasse": einstufung.klasse,
            "rang": einstufung.rang,
            "lesart": einstufung.lesart,
            "rolle": einstufung.rolle,
            "regelwerk_version": einstufung.regelwerk_version,
            "rechtsstand": einstufung.rechtsstand,
            "regelwerk_hash": self.hash(),
            "berechnet_am": einstufung.berechnet_am,
            "ausgeloest_durch": einstufung.ausgeloest_durch,
            "bestandsschutz_greift": einstufung.bestandsschutz_greift,
            "bestandsschutz_hinweis": einstufung.bestandsschutz_hinweis,
            "ausnahmefilter_moeglich": einstufung.ausnahmefilter_moeglich,
            "ausnahmefilter_gesperrt": einstufung.ausnahmefilter_gesperrt_durch_profiling,
            "warnungen": einstufung.warnungen,
            "treffer": [
                {
                    "regel_id": t.regel_id,
                    "klasse": t.klasse,
                    "fundstelle": t.fundstelle,
                    "frist": t.frist,
                    "geprueft": t.geprueft,
                }
                for t in einstufung.treffer
            ],
        }


# ---------------------------------------------------------------------------
# CLI zum schnellen Nachsehen
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    pfad = sys.argv[1] if len(sys.argv) > 1 else "rules/ai-act_2026-07-23.yaml"
    rw = Regelwerk.laden(pfad)
    geprueft, gesamt = rw.pruefstand
    print(f"Regelwerk {rw.version}, Rechtsstand {rw.rechtsstand}")
    print(f"Regeln: {gesamt}, davon verifiziert: {geprueft}")
    print(f"Hash: {rw.hash()[:16]}...")
    print()
    probleme = rw.validieren()
    fehler = [p for p in probleme if p.schwere == "fehler"]
    print(f"Fehler: {len(fehler)}")
    for p in fehler:
        print(f"  [{p.ort}] {p.text}")
    print(f"Ausspielbar: {'ja' if rw.ausspielbar() else 'nein'}")
