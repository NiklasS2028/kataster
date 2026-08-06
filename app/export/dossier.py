"""
export/dossier.py - Nachweis-Dossier als eigenstaendige HTML-Datei.

Bewusst ohne externe Verweise: Stile stehen inline, damit die Datei auch dann
noch vollstaendig ist, wenn sie in fuenf Jahren aus einem Archiv geholt wird.
Ueber Strg+P erzeugt der Browser daraus ein PDF.
"""

from __future__ import annotations

from datetime import datetime
from html import escape

from ..hinweise import als_html

STIL = """
@page { size: A4; margin: 20mm 18mm 22mm; }
* { box-sizing: border-box; }
body { font-family: Georgia, "Times New Roman", serif; font-size: 10.5pt;
       line-height: 1.5; color: #1B1D1A; margin: 0; padding: 24px; max-width: 190mm; }
h1 { font-size: 17pt; margin: 0 0 2px; letter-spacing: -0.01em; }
h2 { font-size: 12pt; margin: 26px 0 8px; padding-bottom: 3px;
     border-bottom: 1.5px solid #1B1D1A; }
h3 { font-size: 10.5pt; margin: 16px 0 5px; }
.kopf { border: 1.5px solid #1B1D1A; padding: 12px 14px; margin-bottom: 22px; }
.kopf dl { display: grid; grid-template-columns: 46mm 1fr; gap: 3px 12px; margin: 0;
           font-family: "Courier New", monospace; font-size: 8.5pt; }
.kopf dt { color: #5A5E57; }
.kopf dd { margin: 0; }
table { width: 100%; border-collapse: collapse; font-size: 9pt; margin: 8px 0 4px; }
th { text-align: left; font-size: 7.5pt; letter-spacing: 0.08em; text-transform: uppercase;
     color: #5A5E57; border-bottom: 1.2px solid #1B1D1A; padding: 4px 6px 4px 0; }
td { border-bottom: 0.5px solid #CFC7B4; padding: 6px 6px 6px 0; vertical-align: top; }
.lfd { font-family: "Courier New", monospace; font-size: 8pt; color: #5A5E57; }
.fund { font-family: "Courier New", monospace; font-size: 8pt; color: #5A5E57; }
.klasse { font-weight: bold; white-space: nowrap; }
.k-verboten { color: #B3312A; }
.k-hochrisiko { color: #A2721F; }
.k-transparenz { color: #45677A; }
.k-minimal { color: #5F7156; }
.hinweis { border-left: 2.5px solid #CFC7B4; padding-left: 10px; margin: 10px 0;
           color: #5A5E57; font-size: 9.5pt; }
.warnung { border: 1.5px solid #B3312A; background: #F6E9E7; padding: 10px 12px;
           margin: 16px 0; font-size: 9.5pt; }
.fuss { margin-top: 28px; padding-top: 10px; border-top: 0.5px solid #CFC7B4;
        font-size: 8.5pt; color: #5A5E57; }
tr, h2, h3 { page-break-inside: avoid; }
h2 { page-break-after: avoid; }
"""


def _z(wert) -> str:
    return escape(str(wert)) if wert not in (None, "") else "&mdash;"


def _eur(wert) -> str:
    """Deutsche Schreibweise: Punkt als Tausender-, Komma als Dezimaltrenner."""
    return f"{float(wert):,.2f}".replace(",", "\u00a0").replace(".", ",").replace("\u00a0", ".")


def _datum(iso: str | None) -> str:
    """ISO-Datum als deutsches Datum. Unbrauchbare Werte bleiben, wie sie sind."""
    try:
        return datetime.strptime(iso, "%Y-%m-%d").strftime("%d.%m.%Y")
    except (TypeError, ValueError):
        return escape(str(iso or ""))


def _lesarten(systeme) -> set[str]:
    """Die Lesarten, in denen die Einstufungen dieses Dossiers gerechnet wurden."""
    return {
        e["lesart"] for s in systeme
        if (e := s.get("einstufung")) and e.get("lesart")
    }


def _rechtsstand_vorbehalt(h: list[str], systeme, regelwerk) -> None:
    """Vorbehalt zum Verhaeltnis zwischen gerechneter Lesart und geltendem Recht.

    Zwei getrennte Vorbehalte, weil beide Lesarten aus verschiedenen Gruenden vom
    geltenden Recht abweichen. Die Lesart original bildet den abgeloesten Stand ab,
    seit die Aenderungsverordnung in Kraft ist. Die Lesart omnibus bildet den neuen
    Stand ab, solange er nur teilweise eingearbeitet ist; ihre Sperre haengt an
    lesarten.omnibus.eingearbeitet und ist von der Verifikation der Regeln
    unabhaengig. ausspielbar() deckt nur letztere und traegt diesen Vorbehalt nicht
    mit: Sind alle Regeln verifiziert, meldet es true, auch wenn der
    Aenderungsrechtsakt offen ist. Ohne den Vorbehalt hier truege ein Dossier in
    Lesart omnibus keinerlei Hinweis darauf, dass die Lesart als unvollstaendig
    ausgewiesen ist.
    """
    omnibus = regelwerk.lesarten.get("omnibus") or {}
    rechtsakt = escape(omnibus.get("rechtsakt") or "der Aenderungsverordnung")
    # Ohne Einstufungen gilt der Ausgangsstand, wie im Erleichterungen-Abschnitt.
    lesarten = _lesarten(systeme) or {"original"}

    if "original" in lesarten and omnibus.get("amtsblatt"):
        h.append("<div class='warnung'><strong>Rechtsstand.</strong> "
                 f"Dieses Dokument enthaelt Einstufungen in der Lesart original, "
                 f"also nach dem Stand vor {rechtsakt}. Der Aenderungsrechtsakt ist seit dem "
                 f"{_datum(omnibus.get('inkrafttreten'))} in Kraft. Die Einstufungen "
                 "bilden insoweit nicht das geltende Recht ab.</div>")

    if "omnibus" in lesarten and omnibus.get("eingearbeitet") is not True:
        h.append("<div class='warnung'><strong>Omnibus-Vorbehalt.</strong> "
                 f"Dieses Dokument enthaelt Einstufungen in der Lesart omnibus. "
                 f"{rechtsakt} ist im "
                 "Regelwerk erst teilweise eingearbeitet: Die unternehmensrelevanten "
                 "Kernaenderungen sind abgebildet und je Regel geprueft, einzelne "
                 "Aenderungsbefehle sind noch nicht entschieden. Der offene Teil ist "
                 "im Regelwerk unter lesarten.omnibus benannt und vor einer "
                 "Verwendung dieses Dokuments selbst zu pruefen.</div>")


def _erleichterungen_abschnitt(h: list[str], organisation, systeme, regelwerk) -> None:
    """Abschnitt 4: groessenabhaengige Erleichterungen nach dem G-Block.

    Ohne Signaturaenderung an dossier_html: alle Eingaben werden aus den bereits
    uebergebenen Objekten abgeleitet. Die Lesart folgt den Einstufungen des uebrigen
    Dossiers (Abschnitt 3 weist sie je System aus), nicht einem festen Wert. Die
    Anzeige ist an den eigenen Pruefstand des G-Blocks gekoppelt: es erscheinen nur
    verifizierte Eintraege (anzeigbare_erleichterungen), ungepruefte nie.
    """
    groessenklasse = organisation.get("groessenklasse")
    hat_partner_verbund = bool(organisation.get("hat_partner_oder_verbund"))
    vorhandene_rollen = {
        e.get("rolle") for s in systeme
        if (e := s.get("einstufung")) and e.get("rolle")
    }
    vorhandene_klassen = {
        e["klasse"] for s in systeme if (e := s.get("einstufung"))
    }
    # Lesart aus den Einstufungen, damit der Abschnitt denselben Rechtsstand fuehrt
    # wie die Einzelnachweise daneben. Bei uneinheitlicher oder fehlender Lesart
    # faellt der Abschnitt auf den Ausgangsstand zurueck; der loest zugleich den
    # Vorbehalt unten aus. Ein gemischter Zustand kann derzeit nicht entstehen,
    # weil die Erfassung nur die Lesart original setzt.
    lesarten = _lesarten(systeme)
    lesart = lesarten.pop() if len(lesarten) == 1 else "original"

    h.append("<h2>4. Erleichterungen nach Unternehmensgroesse</h2>")

    # Anzeige ist nicht Inanspruchnahme. Ein Abschnitt "Erleichterungen" verleitet
    # sonst zur Lesart, das Unternehmen nehme sie bereits in Anspruch (folgenreich
    # etwa bei Art. 11 Abs. 1 UAbs. 2 und Art. 63 Abs. 1).
    h.append("<p>Der Abschnitt weist aus, welche Erleichterungen nach der erfassten "
             "Groessenklasse in Betracht kommen. Er dokumentiert nicht, dass sie in "
             "Anspruch genommen werden, und ersetzt die dafuer jeweils vorgesehenen "
             "Schritte nicht.</p>")

    # Bei Lesart original bildet der Abschnitt einen abgeloesten Rechtsstand ab.
    # In einem Nachweisdokument braucht das einen sichtbaren Vorbehalt.
    if lesart == "original":
        h.append("<p class='hinweis'>Dieser Abschnitt gibt den Rechtsstand vor der "
                 "VO (EU) 2026/1744 wieder (Lesart original) und bildet nicht das "
                 "geltende Recht ab. Die durch den Digital-Omnibus eingefuegten "
                 "Erleichterungen sind hier nicht enthalten.</p>")

    if not groessenklasse:
        h.append("<p class='hinweis'>Fuer die Organisation ist keine Groessenklasse "
                 "erfasst. Ohne Groessenklasse lassen sich die groessenabhaengigen "
                 "Erleichterungen nicht bestimmen.</p>")
    else:
        erleichterungen = regelwerk.anzeigbare_erleichterungen(
            groessenklasse, hat_partner_verbund,
            vorhandene_rollen, vorhandene_klassen, lesart,
        )
        if erleichterungen:
            h.append("<table><thead><tr><th>Gegenstand</th><th>Fundstelle</th>"
                     "<th>Regel</th></tr></thead><tbody>")
            for e in erleichterungen:
                zelle = escape(regelwerk.erleichterung_text(e, lesart))
                if e.get("hinweis"):
                    zelle += f"<br><span class='fund'>{escape(e['hinweis'])}</span>"
                h.append(f"<tr><td><strong>{_z(e.get('gegenstand'))}</strong></td>"
                         f"<td class='fund'>{_z(e.get('fundstelle'))}</td>"
                         f"<td>{zelle}</td></tr>")
            h.append("</tbody></table>")
        elif groessenklasse == "kleines_midcap" and lesart == "original":
            # Kein Treffer aus anderem Grund als bei gross: den Begriff des kleinen
            # Midcap-Unternehmens gab es im Ausgangsrecht nicht.
            h.append("<p class='hinweis'>Fuer die erfasste Groessenklasse kleines "
                     "Midcap greift unter dieser Lesart keine Erleichterung, weil es "
                     "den Begriff des kleinen Midcap-Unternehmens im Ausgangsrecht "
                     "noch nicht gab. Er wird erst durch Art. 3 Nr. 14b KI-VO i. d. F. "
                     "der VO (EU) 2026/1744 eingefuegt.</p>")
        else:
            h.append("<p class='hinweis'>Keine der geprueften Erleichterungen ist "
                     "einschlaegig.</p>")

    # Size-neutrale Zusatzhinweise, je an ihrem eigenen Pruefstand gekoppelt.
    g = regelwerk.groessenregime
    zusatz = []
    zeit = g.get("hinweis_zeitpunkt")
    if isinstance(zeit, dict) and zeit.get("geprueft") is True:
        zusatz.append(("Zeitpunkt des Groessenwechsels.", escape(zeit["text"]), None))
    verh = g.get("hinweis_verhaeltnismaessigkeit")
    if isinstance(verh, dict) and verh.get("geprueft") is True:
        fund = verh.get(f"fundstelle_{lesart}") or verh.get("fundstelle_original")
        zusatz.append(("Verhaeltnismaessigkeit des Qualitaetsmanagements.",
                       escape(verh["text"]), fund))
    unter = g.get("hinweis_unterstuetzung")
    if isinstance(unter, dict) and unter.get("geprueft") is True:
        zusatz.append(("Wo Unterstuetzung zu finden ist.", escape(unter["text"]), None))

    if zusatz:
        h.append("<h3>Ergaenzende Hinweise</h3>")
        for titel, text, fund in zusatz:
            block = f"<p class='hinweis'><strong>{titel}</strong> {text}"
            if fund:
                block += f" <span class='fund'>{escape(fund)}</span>"
            h.append(block + "</p>")


def dossier_html(organisation, systeme, kennzahlen, regelwerk,
                 klassennamen, zeitpunkt: datetime) -> str:
    firma = organisation.get("name") or "[Name des Unternehmens]"
    geprueft, gesamt = regelwerk.pruefstand
    rang = {k: v.get("rang", 0) for k, v in regelwerk.risikoklassen.items()}
    sortiert = sorted(
        systeme,
        key=lambda s: (-rang.get((s.get("einstufung") or {}).get("klasse"), 0), s["name"]),
    )

    h = []
    h.append("<!doctype html><html lang='de'><head><meta charset='utf-8'>")
    h.append(f"<title>KI-Nachweis {escape(firma)} &middot; {zeitpunkt:%Y-%m-%d}</title>")
    h.append(f"<style>{STIL}</style></head><body>")

    h.append(f"<h1>Nachweis zum Einsatz von KI-Systemen</h1>")
    h.append(f"<p>{escape(firma)}</p>")

    h.append("<div class='kopf'><dl>")
    h.append(f"<dt>Erstellt am</dt><dd>{zeitpunkt:%d.%m.%Y, %H:%M} Uhr</dd>")
    h.append(f"<dt>Rechtsstand</dt><dd>{escape(regelwerk.rechtsstand)}</dd>")
    h.append(f"<dt>Regelwerk</dt><dd>{escape(regelwerk.version)}</dd>")
    h.append(f"<dt>Pruefsumme Regelwerk</dt><dd>{regelwerk.hash()[:32]}</dd>")
    h.append(f"<dt>Regeln verifiziert</dt><dd>{geprueft} von {gesamt}</dd>")
    h.append(f"<dt>Erfasste Systeme</dt><dd>{kennzahlen['systeme_gesamt']}</dd>")
    h.append("</dl></div>")

    if not regelwerk.ausspielbar():
        h.append("<div class='warnung'><strong>Entwurfsstand.</strong> "
                 f"Von {gesamt} Regeln sind {geprueft} gegen den amtlichen Text "
                 "verifiziert. Dieses Dokument ist bis zur vollstaendigen "
                 "Verifikation nicht als Nachweis gegenueber Dritten geeignet.</div>")

    _rechtsstand_vorbehalt(h, systeme, regelwerk)

    # Einstufungen, die unter einer aelteren Regelwerksfassung entstanden sind,
    # tragen deren Version und Pruefvermerke. Das ist richtig historisiert -
    # aber ein Dokument, dessen Kopf 1.0.0 sagt und dessen Einzelnachweise
    # 0.3.0 sagen, liest sich als Fehler. Also ausdruecklich benennen.
    veraltet = [
        s for s in systeme
        if s.get("einstufung")
        and s["einstufung"]["regelwerk_version"] != regelwerk.version
    ]
    if veraltet:
        h.append("<div class='warnung'><strong>Abweichende Regelwerksfassung.</strong> "
                 f"{len(veraltet)} von {len(systeme)} Einstufungen wurden mit einer "
                 "aelteren Fassung des Regelwerks berechnet und tragen deshalb deren "
                 "Versionsnummer und Pruefvermerke. Die Angaben sind korrekt "
                 "historisiert, geben aber nicht den aktuellen Stand wieder. "
                 "Vor der Verwendung als Nachweis: neu bewerten.<br><br>"
                 "Betroffen: " + escape(", ".join(s["name"] for s in veraltet))
                 + "</div>")

    h.append("<h2>1. Uebersicht</h2>")
    h.append("<table><thead><tr><th>Einstufung</th><th>Anzahl</th></tr></thead><tbody>")
    for schluessel, bezeichnung in klassennamen.items():
        anzahl = kennzahlen["nach_klasse"].get(schluessel, 0)
        h.append(f"<tr><td class='klasse k-{schluessel}'>{escape(bezeichnung)}</td>"
                 f"<td>{anzahl}</td></tr>")
    if kennzahlen["ohne_einstufung"]:
        h.append(f"<tr><td>Noch nicht eingestuft</td>"
                 f"<td>{kennzahlen['ohne_einstufung']}</td></tr>")
    h.append("</tbody></table>")
    h.append(f"<p class='hinweis'>Erfasster Aufwand fuer KI-Dienste: "
             f"{_eur(kennzahlen['kosten_monat_eur'])} EUR monatlich, "
             f"{_eur(kennzahlen['kosten_jahr_eur'])} EUR im Jahr.</p>")

    h.append("<h2>2. Bestandsverzeichnis</h2>")
    if not sortiert:
        h.append("<p>Es sind keine Systeme erfasst.</p>")
    else:
        h.append("<table><thead><tr><th>Lfd.</th><th>System</th><th>Bereich</th>"
                 "<th>Rolle</th><th>Einstufung</th><th>Ausgeloest durch</th>"
                 "</tr></thead><tbody>")
        for i, s in enumerate(sortiert, start=1):
            e = s.get("einstufung")
            if e:
                klasse = e["klasse"]
                marke = (f"<span class='klasse k-{klasse}'>"
                         f"{escape(klassennamen.get(klasse, klasse))}</span>")
                regeln = ", ".join(e["ausgeloest_durch"]) or "&mdash;"
            else:
                marke, regeln = "nicht erfasst", "&mdash;"
            h.append(f"<tr><td class='lfd'>{i:03d}</td>"
                     f"<td><strong>{_z(s['name'])}</strong><br>{_z(s.get('zweck'))}</td>"
                     f"<td>{_z(s.get('abteilung'))}</td>"
                     f"<td>{_z(s['rolle'])}</td>"
                     f"<td>{marke}</td>"
                     f"<td class='fund'>{regeln}</td></tr>")
        h.append("</tbody></table>")

    h.append("<h2>3. Einzelnachweise</h2>")
    for s in sortiert:
        e = s.get("einstufung")
        if not e:
            continue
        h.append(f"<h3>{_z(s['name'])}</h3>")
        h.append("<table><tbody>")
        h.append(f"<tr><td style='width:46mm'>Einstufung</td>"
                 f"<td class='klasse k-{e['klasse']}'>"
                 f"{escape(klassennamen.get(e['klasse'], e['klasse']))}</td></tr>")
        h.append(f"<tr><td>Berechnet am</td><td>{_z(e['berechnet_am'])}</td></tr>")
        h.append(f"<tr><td>Lesart</td><td>{_z(e['lesart'])}</td></tr>")
        aktuell = e["regelwerk_version"] == regelwerk.version
        vermerk = "" if aktuell else " &mdash; aelter als der Kopfstand"
        h.append(f"<tr><td>Regelwerk</td><td class='fund'>{_z(e['regelwerk_version'])} "
                 f"&middot; {e['regelwerk_hash'][:16]}{vermerk}</td></tr>")
        h.append("</tbody></table>")

        treffer = e["ergebnis"].get("treffer", [])
        if treffer:
            h.append("<table><thead><tr><th>Regel</th><th>Fundstelle</th>"
                     "<th>Frist</th><th>Verifiziert</th></tr></thead><tbody>")
            for t in treffer:
                h.append(f"<tr><td class='lfd'>{escape(t['regel_id'])}</td>"
                         f"<td class='fund'>{_z(t['fundstelle'])}</td>"
                         f"<td class='fund'>{_z(t.get('frist'))}</td>"
                         f"<td>{'ja' if t.get('geprueft') else 'nein'}</td></tr>")
            h.append("</tbody></table>")
        else:
            h.append("<p class='hinweis'>Keine der geprueften Regeln trifft zu.</p>")

        ergebnis = e["ergebnis"]
        if ergebnis.get("abschnitt_b_hinweis"):
            h.append(f"<p class='hinweis'>{escape(ergebnis['abschnitt_b_hinweis'])}</p>")
        if ergebnis.get("bestandsschutz_hinweis"):
            h.append(f"<p class='hinweis'>{escape(ergebnis['bestandsschutz_hinweis'])}</p>")
        if ergebnis.get("ausnahmefilter_gesperrt"):
            h.append("<p class='hinweis'>Die Ausnahme nach Art. 6 Abs. 3 ist "
                     "ausgeschlossen, weil das System ein Profiling vornimmt.</p>")
        elif ergebnis.get("ausnahmefilter_moeglich"):
            h.append("<p class='hinweis'>Fuer dieses System kommt die Ausnahme nach "
                     "Art. 6 Abs. 3 in Betracht. Sie ist gesondert zu begruenden.</p>")

    _erleichterungen_abschnitt(h, organisation, systeme, regelwerk)

    h.append("<h2>5. Grundlagen und Vorbehalt</h2>")
    h.append("<p>Die Einstufungen beruhen auf einem regelbasierten Abgleich der "
             "erfassten Angaben mit dem hinterlegten Regelwerk. Es findet keine "
             "automatisierte Auslegung statt: Jede Einstufung laesst sich auf eine "
             "benannte Regel und deren Fundstelle zurueckfuehren.</p>")
    h.append("<p>Die Richtigkeit der Angaben zu den einzelnen Systemen verantwortet "
             "das erfassende Unternehmen. Werden Angaben unzutreffend gemacht, ist "
             "auch die daraus abgeleitete Einstufung unzutreffend.</p>")
    h.append(f"<div class='fuss'>{als_html()}</div>")
    h.append("</body></html>")
    return "\n".join(h)
