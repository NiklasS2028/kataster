"""
wizard.py - Fuehrt den Nutzer durch die Erfassung eines KI-Systems.

Der Ablauf wird vollstaendig aus dem Regelwerk abgeleitet. Es gibt keine
fest verdrahtete Fragenliste: kommt eine Regel in die YAML, erscheint die
Frage; faellt sie weg, verschwindet sie.

Sechs Abschnitte in fester Reihenfolge:

  1. anwendungsbereich  Faellt das System ueberhaupt unter die Verordnung?
  2. rolle              Betreiber oder Anbieter? Entscheidet, welche
                        Transparenzpflichten ueberhaupt gestellt werden.
  3. verbote            Art. 5. Zuerst, weil ein Treffer alles andere erledigt.
  4. hochrisiko         Anhang I und Anhang III.
  5. transparenz        Art. 50, gefiltert nach Rolle.
  6. bestand            Art. 111. Nur wenn ueberhaupt Hochrisiko im Raum steht.

Ohne Flask, ohne Datenbank - damit die Ablauflogik einzeln testbar bleibt.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

ABSCHNITTE = (
    ("kontext", "Einsatzkontext"),
    ("anwendungsbereich", "Anwendungsbereich"),
    ("rolle", "Ihre Rolle"),
    ("verbote", "Verbotene Praktiken"),
    ("hochrisiko", "Hochrisiko-Einstufung"),
    ("transparenz", "Transparenzpflichten"),
    ("bestand", "Bestandsschutz"),
)


@dataclass
class Frage:
    schluessel: str
    text: str
    abschnitt: str
    typ: str = "ja_nein"          # ja_nein | datum
    fundstelle: str | None = None
    hinweis: str | None = None
    ausnahmen: str | None = None
    optional: bool = False
    optionen: list[dict] | None = None


@dataclass
class Ergebnis:
    """Was der Wizard am Ende an die Einstufung uebergibt."""

    flags: dict[str, bool] = field(default_factory=dict)
    rolle: str = "betreiber"
    in_betrieb_seit: date | None = None
    wesentlich_veraendert: bool = False
    ausserhalb_anwendungsbereich: bool = False
    ausschlussgrund: str | None = None
    ausschluss_fundstelle: str | None = None
    kontexte: list[str] = field(default_factory=list)
    uebersprungene_regeln: list[str] = field(default_factory=list)


class Wizard:
    def __init__(self, regelwerk, ist_behoerde: bool = False):
        self.rw = regelwerk
        self.ist_behoerde = ist_behoerde

    # -- Fragenkatalog -------------------------------------------------------

    def _fragen_kontext(self) -> list[Frage]:
        ek = self.rw.einsatzkontexte
        if not ek:
            return []
        return [
            Frage(
                schluessel="kontext",
                text="In welchen Bereichen wird das System eingesetzt?",
                abschnitt="kontext",
                typ="mehrfachauswahl",
                hinweis=ek.get("hinweis"),
                optionen=ek.get("definitionen", []),
            )
        ]

    def _kontexte_aus(self, antworten: dict[str, Any]) -> list[str]:
        roh = antworten.get("kontext")
        if isinstance(roh, str):
            return [roh]
        return list(roh or [])

    def _regel_im_kontext(self, regel_id: str, kontexte: list[str]) -> bool:
        """Regeln ohne Zuordnung werden immer gestellt."""
        zuordnung = self.rw.einsatzkontexte.get("zuordnung", {})
        noetig = zuordnung.get(regel_id)
        if not noetig:
            return True
        return bool(set(noetig) & set(kontexte))

    def _fragen_anwendungsbereich(self) -> list[Frage]:
        fragen = []
        for a in self.rw.anwendungsbereich:
            fragen.append(
                Frage(
                    schluessel=f"ab:{a['id']}",
                    text=a["frage"],
                    abschnitt="anwendungsbereich",
                    fundstelle=a.get("fundstelle"),
                    hinweis=a.get("hinweis") or a.get("folge"),
                )
            )
        return fragen

    def _fragen_rolle(self) -> list[Frage]:
        fragen = []
        for r in self.rw.rollenbestimmung.get("fragen", []):
            fragen.append(
                Frage(
                    schluessel=f"rolle:{r['id']}",
                    text=r["text"],
                    abschnitt="rolle",
                    fundstelle=r.get("fundstelle"),
                    hinweis=r.get("hinweis"),
                )
            )
        return fragen

    def _regelfragen(
        self, abschnitt: str, rolle: str, kontexte: list[str]
    ) -> list[Frage]:
        klassen = {
            "verbote": {"verboten"},
            "hochrisiko": {"hochrisiko"},
            "transparenz": {"transparenz"},
        }[abschnitt]

        fragen = []
        for regel in self.rw.regeln:
            if regel["klasse"] not in klassen:
                continue

            rollen = regel.get("nur_bei_rolle")
            if rollen and rolle not in rollen and rolle != "beides":
                continue

            if not self._regel_im_kontext(regel["id"], kontexte):
                continue

            fragen.append(
                Frage(
                    schluessel=f"flag:{regel['trifft_zu_wenn']}",
                    text=regel["frage"],
                    abschnitt=abschnitt,
                    fundstelle=regel["fundstelle"],
                    hinweis=regel.get("hinweis"),
                    ausnahmen=regel.get("ausnahmen"),
                )
            )

            zusatz = regel.get("zusatzbedingung")
            if zusatz:
                fragen.append(
                    Frage(
                        schluessel=f"flag:{zusatz['trifft_zu_wenn']}",
                        text=zusatz["frage"],
                        abschnitt=abschnitt,
                        fundstelle=regel["fundstelle"],
                        hinweis="Folgefrage. Nur relevant, wenn die vorige Frage bejaht wurde.",
                        optional=True,
                    )
                )

        # Sperrflag des Ausnahmefilters mit abfragen - es entscheidet, ob die
        # Ausnahme nach Art. 6 Abs. 3 ueberhaupt geprueft werden darf.
        if abschnitt == "hochrisiko" and fragen:
            sperr = self.rw.ausnahmefilter.get("gilt_nicht_bei")
            if sperr:
                fragen.append(
                    Frage(
                        schluessel=f"flag:{sperr}",
                        text=(
                            "Nimmt das System ein Profiling natuerlicher Personen "
                            "vor, also eine automatisierte Auswertung persoenlicher "
                            "Aspekte zur Bewertung oder Vorhersage?"
                        ),
                        abschnitt="hochrisiko",
                        fundstelle=self.rw.ausnahmefilter.get("fundstelle"),
                        hinweis=self.rw.ausnahmefilter.get("sperrhinweis"),
                    )
                )
        return fragen

    def _fragen_bestand(self) -> list[Frage]:
        return [
            Frage(
                schluessel="bestand:in_betrieb_seit",
                text="Seit wann ist das System bei Ihnen in Betrieb?",
                abschnitt="bestand",
                typ="datum",
                fundstelle="Art. 111 Abs. 2 KI-VO",
                hinweis=(
                    "Systeme, die vor dem allgemeinen Geltungsbeginn in Betrieb "
                    "genommen wurden, koennen unter den Bestandsschutz fallen."
                ),
                optional=True,
            ),
            Frage(
                schluessel="bestand:wesentlich_veraendert",
                text=(
                    "Wurde das System seitdem in seiner Konzeption wesentlich "
                    "veraendert?"
                ),
                abschnitt="bestand",
                fundstelle="Art. 3 Nr. 23 KI-VO",
                hinweis=(
                    "Eine wesentliche Veraenderung laesst den Bestandsschutz "
                    "entfallen."
                ),
            ),
        ]

    # -- Ablaufsteuerung -----------------------------------------------------

    def _rolle_aus(self, antworten: dict[str, Any]) -> str:
        anbieter = False
        for r in self.rw.rollenbestimmung.get("fragen", []):
            if antworten.get(f"rolle:{r['id']}") and r.get("wenn_ja") == "anbieter":
                anbieter = True
        betreiber = bool(antworten.get("rolle:R-01"))
        if anbieter and betreiber:
            return "beides"
        if anbieter:
            return "anbieter"
        return "betreiber"

    def _ausschluss(self, antworten: dict[str, Any]) -> dict[str, Any] | None:
        for a in self.rw.anwendungsbereich:
            if not antworten.get(f"ab:{a['id']}"):
                continue
            # A-04 (Open Source) greift nur, wenn keine Hochrisiko- oder
            # Art.-5/50-Betroffenheit vorliegt. Das steht erst am Ende fest,
            # deshalb kein harter Abbruch, sondern eine Notiz.
            if a.get("bedingt"):
                continue
            return a
        return None

    def alle_fragen(self, antworten: dict[str, Any]) -> list[Frage]:
        """Der vollstaendige Fragebogen im aktuellen Antwortstand."""
        fragen = list(self._fragen_kontext())

        # Ohne Kontextauswahl steht der weitere Ablauf noch nicht fest.
        if "kontext" not in antworten:
            return fragen

        fragen += self._fragen_anwendungsbereich()

        if self._ausschluss(antworten):
            return fragen

        fragen += self._fragen_rolle()
        rolle = self._rolle_aus(antworten)
        kontexte = self._kontexte_aus(antworten)

        fragen += self._regelfragen("verbote", rolle, kontexte)
        fragen += self._regelfragen("hochrisiko", rolle, kontexte)
        fragen += self._regelfragen("transparenz", rolle, kontexte)

        if self._hochrisiko_moeglich(antworten):
            fragen += self._fragen_bestand()

        sichtbar = [f for f in fragen if self._frage_sichtbar(f, antworten, fragen)]

        # Mehrere Regeln koennen dasselbe Flag verwenden - etwa
        # emotionserkennung_sonstige, das sowohl H-09 (Hochrisiko) als auch
        # T-04 (Transparenzpflicht) ausloest. Gefragt wird trotzdem nur einmal,
        # und zwar an der fruehesten Stelle im Ablauf.
        gesehen: set[str] = set()
        eindeutig = []
        for f in sichtbar:
            if f.schluessel in gesehen:
                continue
            gesehen.add(f.schluessel)
            eindeutig.append(f)
        return eindeutig

    def _frage_sichtbar(
        self, frage: Frage, antworten: dict[str, Any], alle: list[Frage]
    ) -> bool:
        """Folgefragen erscheinen nur, wenn die vorausgehende bejaht wurde."""
        if not frage.optional or frage.abschnitt == "bestand":
            return True
        index = next(
            (i for i, f in enumerate(alle) if f.schluessel == frage.schluessel), None
        )
        if index is None or index == 0:
            return True
        vorgaenger = alle[index - 1]
        return bool(antworten.get(vorgaenger.schluessel))

    def _hochrisiko_moeglich(self, antworten: dict[str, Any]) -> bool:
        for regel in self.rw.regeln:
            if regel["klasse"] != "hochrisiko":
                continue
            if antworten.get(f"flag:{regel['trifft_zu_wenn']}"):
                return True
        return False

    def naechste_frage(self, antworten: dict[str, Any]) -> Frage | None:
        for frage in self.alle_fragen(antworten):
            if frage.schluessel not in antworten:
                return frage
        return None

    def fortschritt(self, antworten: dict[str, Any]) -> tuple[int, int]:
        fragen = self.alle_fragen(antworten)
        beantwortet = sum(1 for f in fragen if f.schluessel in antworten)
        return beantwortet, len(fragen)

    def abschnitt_stand(self, antworten: dict[str, Any]) -> list[dict[str, Any]]:
        """Fuer die Fortschrittsanzeige im UI."""
        fragen = self.alle_fragen(antworten)
        stand = []
        for schluessel, titel in ABSCHNITTE:
            teil = [f for f in fragen if f.abschnitt == schluessel]
            if not teil:
                continue
            fertig = sum(1 for f in teil if f.schluessel in antworten)
            stand.append(
                {
                    "schluessel": schluessel,
                    "titel": titel,
                    "fragen": len(teil),
                    "beantwortet": fertig,
                    "abgeschlossen": fertig == len(teil),
                }
            )
        return stand

    # -- Auswertung ----------------------------------------------------------

    def auswerten(self, antworten: dict[str, Any]) -> Ergebnis:
        ergebnis = Ergebnis()

        ausschluss = self._ausschluss(antworten)
        if ausschluss:
            ergebnis.ausserhalb_anwendungsbereich = True
            ergebnis.ausschlussgrund = ausschluss.get("folge")
            ergebnis.ausschluss_fundstelle = ausschluss.get("fundstelle")
            return ergebnis

        ergebnis.rolle = self._rolle_aus(antworten)
        ergebnis.kontexte = self._kontexte_aus(antworten)
        ergebnis.uebersprungene_regeln = [
            r["id"]
            for r in self.rw.regeln
            if not self._regel_im_kontext(r["id"], ergebnis.kontexte)
        ]

        for schluessel, wert in antworten.items():
            if schluessel.startswith("flag:"):
                ergebnis.flags[schluessel[5:]] = bool(wert)

        rohdatum = antworten.get("bestand:in_betrieb_seit")
        if rohdatum:
            try:
                ergebnis.in_betrieb_seit = (
                    rohdatum
                    if isinstance(rohdatum, date)
                    else date.fromisoformat(str(rohdatum))
                )
            except ValueError:
                ergebnis.in_betrieb_seit = None

        ergebnis.wesentlich_veraendert = bool(
            antworten.get("bestand:wesentlich_veraendert")
        )
        return ergebnis


if __name__ == "__main__":
    import sys

    sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
    from regelwerk import Regelwerk

    rw = Regelwerk.laden("rules/ai-act_2026-07-27.yaml")
    w = Wizard(rw)

    antworten: dict[str, Any] = {}
    print("Leerer Stand:", w.fortschritt(antworten), "Fragen")
    print("Erste Frage:", w.naechste_frage(antworten).text[:70], "...")
