"""
export/dossier.py - Nachweis-Dossier als eigenstaendige HTML-Datei.

Bewusst ohne externe Verweise: Stile stehen inline, damit die Datei auch dann
noch vollstaendig ist, wenn sie in fuenf Jahren aus einem Archiv geholt wird.
Ueber Strg+P erzeugt der Browser daraus ein PDF.
"""

from __future__ import annotations

from datetime import datetime
from html import escape

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
             f"{kennzahlen['kosten_monat_eur']:.2f} EUR monatlich, "
             f"{kennzahlen['kosten_jahr_eur']:.2f} EUR im Jahr.</p>")

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
        h.append(f"<tr><td>Regelwerk</td><td class='fund'>{_z(e['regelwerk_version'])} "
                 f"&middot; {e['regelwerk_hash'][:16]}</td></tr>")
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
        if ergebnis.get("bestandsschutz_hinweis"):
            h.append(f"<p class='hinweis'>{escape(ergebnis['bestandsschutz_hinweis'])}</p>")
        if ergebnis.get("ausnahmefilter_gesperrt"):
            h.append("<p class='hinweis'>Die Ausnahme nach Art. 6 Abs. 3 ist "
                     "ausgeschlossen, weil das System ein Profiling vornimmt.</p>")
        elif ergebnis.get("ausnahmefilter_moeglich"):
            h.append("<p class='hinweis'>Fuer dieses System kommt die Ausnahme nach "
                     "Art. 6 Abs. 3 in Betracht. Sie ist gesondert zu begruenden.</p>")

    h.append("<h2>4. Grundlagen und Vorbehalt</h2>")
    h.append("<p>Die Einstufungen beruhen auf einem regelbasierten Abgleich der "
             "erfassten Angaben mit dem hinterlegten Regelwerk. Es findet keine "
             "automatisierte Auslegung statt: Jede Einstufung laesst sich auf eine "
             "benannte Regel und deren Fundstelle zurueckfuehren.</p>")
    h.append("<p>Die Richtigkeit der Angaben zu den einzelnen Systemen verantwortet "
             "das erfassende Unternehmen. Werden Angaben unzutreffend gemacht, ist "
             "auch die daraus abgeleitete Einstufung unzutreffend.</p>")
    h.append("<div class='fuss'><strong>Kein Rechtsrat.</strong> Kataster ist ein "
             "Werkzeug zur strukturierten Selbsteinschaetzung und Dokumentation. Es "
             "trifft keine rechtliche Bewertung, bescheinigt keine Konformitaet und "
             "ersetzt keine Beratung. Verbindlich sind allein die im Amtsblatt der "
             "Europaeischen Union veroeffentlichten Texte (Art. 297 AEUV).</div>")
    h.append("</body></html>")
    return "\n".join(h)
