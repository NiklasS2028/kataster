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
    abschnitt_b_greift: bool = False
    abschnitt_b_hinweis: str | None = None
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
        self.anhang_i: dict = daten.get("anhang_i", {})
        self.anwendungsbereich: list[dict] = daten.get("anwendungsbereich_ausnahmen", [])
        self.einsatzkontexte: dict[str, Any] = daten.get("einsatzkontexte", {})
        self.schulungsbausteine: list[dict] = daten.get("schulungsbausteine", [])
        self.groessenregime: dict[str, Any] = daten.get("groessenregime", {})
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

    @property
    def groessenregime_pruefstand(self) -> tuple[int, int]:
        """(geprueft, gesamt) ueber alle Verifikationseinheiten des G-Blocks.

        Einheiten: die Definitionen (eine Einheit, verifiziert nur wenn beide
        Eintraege es sind), die drei Hinweisbloecke mit je eigenem geprueft und
        jede Erleichterung. Eigene Achse neben pruefstand: der G-Block hat seinen
        eigenen Verifikationsstand und blockiert die uebrigen Exporte nicht. So
        bleibt jede Einheit eintragsweise freigebbar.
        """
        g = self.groessenregime
        flags: list[bool] = []

        defs = g.get("definitionen") or []
        if defs:
            flags.append(all(d.get("geprueft") is True for d in defs))

        for schluessel in (
            "hinweis_zeitpunkt",
            "hinweis_unterstuetzung",
            "hinweis_verhaeltnismaessigkeit",
        ):
            block = g.get(schluessel)
            if isinstance(block, dict) and "geprueft" in block:
                flags.append(block["geprueft"] is True)

        for e in g.get("erleichterungen", []):
            flags.append(e.get("geprueft") is True)

        return sum(flags), len(flags)

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

        # Groessenregime: Erleichterungen strukturell pruefen. Der Regeltext
        # muss aufloesbar sein (text, lesart_* oder Zeiger). Ein Zeiger auf ein
        # noch fehlendes Zielfeld ist ein bewusster Uebergangszustand und wird
        # als Hinweis gemeldet, nicht als Fehler oder Warnung, damit die Kopplung
        # von ausspielbar() an den Regel-Pruefstand unveraendert bleibt.
        g_ids: set[str] = set()
        for e in self.groessenregime.get("erleichterungen", []):
            ort = f"groessenregime/{e.get('id', '???')}"
            eid = e.get("id")
            if not eid:
                probleme.append(Problem("fehler", ort, "Feld 'id' fehlt."))
            if eid in g_ids:
                probleme.append(Problem("fehler", ort, "Doppelte Erleichterungs-ID."))
            g_ids.add(eid)

            if not e.get("fundstelle"):
                probleme.append(Problem("fehler", ort, "Feld 'fundstelle' fehlt."))

            for l in e.get("gilt_in_lesart") or []:
                if l not in LESARTEN:
                    probleme.append(
                        Problem("fehler", ort, f"Unbekannte Lesart '{l}' in 'gilt_in_lesart'.")
                    )

            gfg = e.get("gilt_fuer_groesse")
            if isinstance(gfg, dict):
                for k in gfg:
                    if k not in LESARTEN:
                        probleme.append(
                            Problem("fehler", ort, f"Unbekannter Lesart-Schluessel '{k}' in 'gilt_fuer_groesse'.")
                        )

            ziel_id = e.get("verweist_auf")
            if ziel_id:
                ziel = next(
                    (q for q in self.querschnittspflichten if q.get("id") == ziel_id),
                    None,
                )
                feld = e.get("verweist_auf_feld")
                if ziel is None:
                    probleme.append(
                        Problem("fehler", ort, f"Zeigerziel '{ziel_id}' existiert nicht.")
                    )
                elif not feld:
                    probleme.append(Problem("fehler", ort, "Zeiger ohne 'verweist_auf_feld'."))
                elif not ziel.get(feld):
                    probleme.append(
                        Problem("hinweis", ort, f"Zeigerziel {ziel_id}.{feld} noch nicht vorhanden (Folgecommit).")
                    )
            else:
                hat_text = bool(
                    e.get("text") or e.get("lesart_original") or e.get("lesart_omnibus")
                )
                if not hat_text:
                    probleme.append(
                        Problem("fehler", ort, "Kein Regeltext: weder 'text', 'lesart_*' noch Zeiger.")
                    )

        # Groessenregime: die uebrigen Verifikationseinheiten muessen je ein
        # eigenes geprueft tragen, damit sie eintragsweise freigebbar sind und
        # der Pruefstand sie zaehlt. Der frueher geteilte Schalter auf
        # Blockebene ist damit zerlegt.
        for d in self.groessenregime.get("definitionen") or []:
            if "geprueft" not in d:
                probleme.append(
                    Problem(
                        "fehler",
                        f"groessenregime/definition/{d.get('klasse', '?')}",
                        "Feld 'geprueft' fehlt.",
                    )
                )
        for schluessel in (
            "hinweis_zeitpunkt",
            "hinweis_unterstuetzung",
            "hinweis_verhaeltnismaessigkeit",
        ):
            block = self.groessenregime.get(schluessel)
            if block is not None and not (
                isinstance(block, dict) and "geprueft" in block
            ):
                probleme.append(
                    Problem(
                        "fehler",
                        f"groessenregime/{schluessel}",
                        "Verifikationseinheit ohne eigenes 'geprueft'.",
                    )
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
        """True nur, wenn kein Fehler und keine ungeprueften Regeln vorliegen.

        Bezieht sich auf den globalen Export der Regeln. Der G-Block hat einen
        eigenen Pruefstand und geht hier bewusst NICHT ein: ein unverifizierter
        G-Block soll nicht die 28 verifizierten Regeln mit anhalten. Fuer den
        Zustand des G-Blocks siehe freigabestatus und groessenregime_pruefstand.
        """
        return not any(p.schwere in ("fehler", "warnung") for p in self.validieren())

    def freigabestatus(self) -> dict[str, Any]:
        """Weist aus, was ausgespielt werden darf, ohne global zu blockieren.

        ausspielbar deckt den globalen Regel-Export. Der G-Block wird getrennt
        ausgewiesen: seine Erleichterungen erscheinen erst im Dossier, wenn sie
        einzeln verifiziert sind (siehe anzeigbare_erleichterungen). So bleibt
        sichtbar, dass der G-Block noch ungeprueft ist, statt es zu verschweigen
        oder alles anzuhalten.
        """
        g_geprueft, g_gesamt = self.groessenregime_pruefstand
        return {
            "ausspielbar": self.ausspielbar(),
            "regeln_pruefstand": self.pruefstand,
            "groessenregime_pruefstand": (g_geprueft, g_gesamt),
            "groessenregime_vollstaendig_geprueft": g_gesamt > 0 and g_geprueft == g_gesamt,
        }

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

        self._abschnitt_b_pruefen(einstufung, flags)
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

        # Fuer Abschnitt B gilt Kapitel III nicht, es gibt also keinen
        # Geltungsbeginn, an den Art. 111 Abs. 2 anknuepfen koennte.
        if einstufung.abschnitt_b_greift:
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

    def _abschnitt_b_pruefen(
        self, einstufung: Einstufung, flags: dict[str, bool]
    ) -> None:
        if einstufung.klasse != "hochrisiko":
            return
        if not any(t.regel_id in ("P-01", "P-02") for t in einstufung.treffer):
            return
        if not flags.get("anhang_i_abschnitt_b", False):
            return

        abschnitt = (self.anhang_i or {}).get("abschnitt_b", {})
        einstufung.abschnitt_b_greift = True
        einstufung.abschnitt_b_hinweis = (
            "Das Produkt faellt unter Anhang I Abschnitt B. Die Einstufung als "
            "hochrisiko bleibt bestehen, das Pflichtenregime ist aber ein "
            "anderes: " + abschnitt.get("rechtsfolge", "").strip() + " "
            "Offen ist, ob und wie der Bestandsschutz nach Art. 111 Abs. 2 hier "
            "greift - die Verordnung sagt dazu nichts ausdruecklich. Er wird "
            "deshalb nicht berechnet."
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

    # -- Groessenregime ------------------------------------------------------

    @staticmethod
    def _groesse_fuer_lesart(wert: Any, lesart: str) -> list[str]:
        """Loest gilt_fuer_groesse auf: flache Liste ODER Dict {original, omnibus}.

        Der Dict-Fall tritt auf, wenn sich der erfasste Groessenkreis mit der
        Lesart aendert (z. B. G-01: original nur KMU, omnibus auch Midcaps).
        """
        if isinstance(wert, dict):
            return wert.get(lesart, []) or []
        return wert or []

    def erleichterungen_fuer(
        self,
        groessenklasse: str | None,
        hat_partner_verbund: bool,
        vorhandene_rollen: set[str],
        vorhandene_klassen: set[str],
        lesart: str = "original",
    ) -> list[dict]:
        """Filtert die groessenabhaengigen Erleichterungen fuer eine Organisation.

        Roher Struktur- und Lesart-Filter OHNE Pruefstand-Kopplung. Fuer die
        Anzeige im Dossier anzeigbare_erleichterungen verwenden, das zusaetzlich
        ungepruefte Eintraege ausschliesst.

        Rein deklarativ: die Bedingungen stehen im YAML, hier wird nur
        abgeglichen. Ohne erfasste Groessenklasse gibt es nichts zu zeigen. Eine
        Erleichterung, die nur Anbieter von Hochrisiko-Systemen trifft, laeuft
        fuer einen reinen Betreiber leer und wird ausgelassen. Der erfasste Kreis
        und die Verfuegbarkeit einer Erleichterung koennen von der Lesart
        abhaengen (gilt_fuer_groesse als Dict, gilt_in_lesart).
        """
        if lesart not in LESARTEN:
            raise ValueError(f"Unbekannte Lesart: {lesart}")
        if not groessenklasse:
            return []
        # Ein System der Rolle "beides" ist zugleich Anbieter und Betreiber.
        effektive_rollen = set(vorhandene_rollen)
        if "beides" in effektive_rollen:
            effektive_rollen |= {"anbieter", "betreiber"}

        treffer: list[dict] = []
        for e in self.groessenregime.get("erleichterungen", []):
            gilt_lesart = e.get("gilt_in_lesart")
            if gilt_lesart and lesart not in gilt_lesart:
                continue
            klassen_groesse = self._groesse_fuer_lesart(
                e.get("gilt_fuer_groesse"), lesart
            )
            if groessenklasse not in klassen_groesse:
                continue
            rollen = e.get("gilt_fuer")
            if rollen and not (set(rollen) & effektive_rollen):
                continue
            klassen = e.get("nur_bei_klasse")
            if klassen and not (set(klassen) & vorhandene_klassen):
                continue
            if e.get("setzt_kein_partner_verbund_voraus") and hat_partner_verbund:
                continue
            treffer.append(e)
        return treffer

    def erleichterung_text(self, e: dict, lesart: str = "original") -> str:
        """Effektiver Regeltext einer Erleichterung fuer die Anzeige.

        Drei Formen: flacher 'text', Dict-Fall ('lesart_original'/'lesart_omnibus')
        oder Zeiger ('verweist_auf' auf ein Feld einer Querschnittspflicht). Ein
        Zeiger ohne auffindbares Ziel wird sichtbar gemeldet, nie leer
        zurueckgegeben, damit eine bewusst offene Stelle (z. B. Q-02.midcap_regel
        vor dem Folgecommit) auffaellt statt still zu verschwinden.
        """
        if lesart not in LESARTEN:
            raise ValueError(f"Unbekannte Lesart: {lesart}")

        ziel_id = e.get("verweist_auf")
        if ziel_id:
            feld = e.get("verweist_auf_feld")
            ziel = next(
                (q for q in self.querschnittspflichten if q.get("id") == ziel_id),
                None,
            )
            if ziel is None:
                return f"[Zeigerziel {ziel_id} nicht gefunden]"
            if not feld:
                return f"[Zeiger auf {ziel_id} ohne Feldangabe]"
            wert = ziel.get(feld)
            if not wert:
                return (
                    f"[Regeltext {ziel_id}.{feld} noch nicht vorhanden, "
                    "folgt im Folgecommit]"
                )
            return wert

        lesart_feld = e.get(f"lesart_{lesart}")
        if lesart_feld:
            return lesart_feld

        return e.get("text", "")

    def _zeigerziel_geprueft(self, e: dict) -> bool:
        """True, wenn ein Eintrag kein Zeiger ist oder sein Zielfeld verifiziert ist.

        Der geprueft-Schalter eines Zeiger-Eintrags (G-06/G-07) zertifiziert nur
        die Verdrahtung, nicht den Wortlaut, der aus dem Zielfeld gerendert wird.
        Ohne diese Pruefung waere die Anzeige-Kopplung bei Zeigern wirkungslos: ein
        verifizierter Zeiger koennte unverifizierten Zieltext ausspielen. Der
        Pruefstand des Zielfelds liegt feldweise als '<feld>_geprueft' vor.
        """
        ziel_id = e.get("verweist_auf")
        if not ziel_id:
            return True
        feld = e.get("verweist_auf_feld")
        if not feld:
            return False
        ziel = next(
            (q for q in self.querschnittspflichten if q.get("id") == ziel_id),
            None,
        )
        if ziel is None:
            return False
        return ziel.get(f"{feld}_geprueft") is True

    def anzeigbare_erleichterungen(
        self,
        groessenklasse: str | None,
        hat_partner_verbund: bool,
        vorhandene_rollen: set[str],
        vorhandene_klassen: set[str],
        lesart: str = "original",
    ) -> list[dict]:
        """Nur die fuer die Anzeige freigegebenen Erleichterungen.

        Koppelt die Dossier-Anzeige an den eigenen Pruefstand des G-Blocks: ein
        Eintrag mit geprueft: false erscheint nicht, unabhaengig von ausspielbar().
        Bei Zeiger-Eintraegen wird zusaetzlich das Zielfeld mitgeprueft
        (_zeigerziel_geprueft), sonst spielte ein verifizierter Zeiger ueber ein
        unverifiziertes Zielfeld unverifizierten Text aus. So geraten keine
        ungeprueften Rechtsformulierungen in ein Nachweisdokument, waehrend die
        uebrigen Exporte moeglich bleiben. Das Dossier ruft diese Methode, nicht
        erleichterungen_fuer.
        """
        return [
            e
            for e in self.erleichterungen_fuer(
                groessenklasse,
                hat_partner_verbund,
                vorhandene_rollen,
                vorhandene_klassen,
                lesart,
            )
            if e.get("geprueft") is True and self._zeigerziel_geprueft(e)
        ]

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
            "abschnitt_b_greift": einstufung.abschnitt_b_greift,
            "abschnitt_b_hinweis": einstufung.abschnitt_b_hinweis,
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
    g_geprueft, g_gesamt = rw.groessenregime_pruefstand
    print(f"Regelwerk {rw.version}, Rechtsstand {rw.rechtsstand}")
    print(f"Regeln: {gesamt}, davon verifiziert: {geprueft}")
    print(f"Groessenregime: {g_gesamt} Verifikationseinheiten, davon verifiziert: {g_geprueft}")
    print(f"Hash: {rw.hash()[:16]}...")
    print()
    probleme = rw.validieren()
    fehler = [p for p in probleme if p.schwere == "fehler"]
    print(f"Fehler: {len(fehler)}")
    for p in fehler:
        print(f"  [{p.ort}] {p.text}")
    print(f"Ausspielbar: {'ja' if rw.ausspielbar() else 'nein'}")
