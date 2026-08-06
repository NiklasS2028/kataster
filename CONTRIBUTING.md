# Mitarbeit

Kataster hat eine ungewöhnliche Eigenschaft: Der Wert des Projekts liegt nicht
im Code, sondern in der Regelwerksdatei unter `rules/` und darin, dass jede
Regel gegen den amtlichen Normtext gelesen wurde. Der Code kennt keinen
einzigen Paragraphen; er wertet nur aus, was in der YAML steht. Deshalb sind
die Konventionen für das Regelwerk strenger als die für den Code.

Wer hier mitarbeitet, sollte die drei folgenden Abschnitte gelesen haben, bevor
er die YAML anfasst.

---

## Der Prüfvermerk

**Neue oder geänderte Einträge entstehen mit `geprueft: false`.** Erst wenn
jemand den amtlichen Normtext selbst gelesen und mit dem Eintrag verglichen
hat, wird `geprueft: true` gesetzt, zusammen mit `geprueft_am` (ISO-Datum) und
`geprueft_von` (Name).

`geprueft_von` behauptet, dass diese Person geprüft hat. Der Vermerk wird
deshalb **nie stellvertretend** gesetzt, auch nicht, wenn die Sache eindeutig
aussieht.

Das gilt besonders für maschinelle Zuarbeit. Wenn ein Werkzeug oder ein
Assistent einen Eintrag nach eigenem Abgleich als sauber bezeichnet, ist das
eine Einschätzung, keine Freigabe. Die Einschätzung kann ausführlich begründet
sein und trotzdem falsch. Bei den Fristen, bei V-07 und bei der Teilung von
P-01 und P-02 hat genau diese Trennung echte Fehler gefunden.

Die Verifikation ist ein eigener, datierter Commit, getrennt vom
Strukturumbau. Wer beides mischt, kann hinterher nicht mehr sagen, welcher
Stand gelesen wurde.

Praktisch: `python tools/verifizieren.py --arbeitsliste` erzeugt eine nach
Fundstelle gruppierte Liste, damit jede Normstelle nur einmal aufgeschlagen
werden muss. Nach der Lektüre setzt
`python tools/verifizieren.py V-01 V-02 --von "Name"` die Vermerke.

### Wann eine Änderung den Vermerk zurücksetzt

**Zurücksetzen** bei jeder Änderung, die Fundstelle, Größenklasse, Rechtsfolge
oder die Aussage über den Rechtsstand berührt. Also bei allem, was den
Normbezug oder die rechtliche Aussage verschiebt.

**Nicht zurücksetzen** bei rein darstellenden Änderungen: Zeichensetzung,
Zeilenumbruch, HTML-Entities, Leerraum, Formatierung ohne
Bedeutungsverschiebung.

**Im Zweifel zurücksetzen.** Ein gerade freigegebenes Feld nur für Typografie
anzufassen ist der schlechtere Handel: Der Aufwand einer erneuten Lektüre ist
klein, ein Prüfvermerk, der auf einen anderen Wortlaut zeigt als den gelesenen,
ist ein stiller Fehler.

---

## Lesarten und der Marker „i. d. F."

Das Regelwerk führt zwei Lesarten: `original` (Verordnung (EU) 2024/1689) und
`omnibus` (dieselbe Verordnung in der Fassung der Verordnung (EU) 2026/1744).

**Die Basisfelder einer Regel beschreiben den ursprünglichen Rechtsstand.** Das
gilt für `fundstelle`, `lesart_original` und alle übrigen lesartenfähigen
Felder. Die Änderung durch den Digital-Omnibus steht ausschließlich in
`lesart_omnibus` beziehungsweise wird über `gilt_in_lesart` geführt.

Ein Marker wie „i. d. F. der VO (EU) 2026/1744" gehört deshalb **nicht** in ein
lesartenfähiges Basisfeld. Sonst verweist die Regel im Zustand `original` auf
eine Fassung, die es zu diesem Rechtsstand noch nicht gab, und die Angabe der
Lesart original wird falsch.

Korrekt ist der Marker nur in Blöcken ohne Lesarten-Mechanismus, die
ausschließlich den Stand nach dem Omnibus beschreiben, etwa
`anhang_i.abschnitt_b.fundstelle` oder Einträge unter `quellen`.

Fällt ein solcher Marker in einem lesartenfähigen Basisfeld auf, ist das ein
eigener Befund: sammeln und melden, nicht nebenbei ändern. Erwägungsgründe als
Auslegungshilfe kommen in ein `anmerkung`-Feld, wo die Regel eines hat (wie
P-02 mit Erwägungsgrund 7), sonst in `hinweis_praxis` (wie Q-01 mit
Erwägungsgrund 8).

---

## Konventionen der Regelwerksdatei

- **ASCII-Transliteration.** Die YAML enthält keine Umlaute: `ae`, `oe`, `ue`,
  `ss`. Die Datei wird eigenständig weitergegeben und soll in jeder Umgebung
  gleich lesbar sein. Für Dokumentation und Oberfläche gilt das nicht, dort
  wird normal geschrieben.
- **Kein YAML-Roundtrip.** Die Werkzeuge unter `tools/` bearbeiten die Datei
  zeilenweise als Text. Ein Serialisieren über `yaml.dump` würde die Kommentare
  vernichten, und die Kommentare sind Teil des Werts: In ihnen steht, warum ein
  Eintrag so aussieht, wie er aussieht.
- **Bewusste Auslassungen sind Einträge, keine Kommentare.** Was nicht
  abgebildet wird, steht mit Begründung unter `omnibus_auslassungen`
  beziehungsweise als Kommentar am jeweiligen Block. Eine Auslassung, die
  nirgends steht, ist von einem Versehen nicht zu unterscheiden.
- Nach jeder Änderung: `python -c "import yaml; yaml.safe_load(open(...))"`
  und `python -m pytest`.

---

## Code

Ein Grundsatz: **Rechtswissen gehört nicht in den Code.** Wenn eine Änderung
einen Artikel, eine Frist oder eine Risikoklasse in eine `.py`-Datei schreiben
will, ist meistens die YAML der richtige Ort. `app/regelwerk.py` wertet aus,
es weiß nichts.

Was daraus folgt:

- Die Einstufung bleibt regelbasiert und deterministisch. Kein Modellaufruf,
  keine Heuristik. Ein Nachweis-Dossier ist nur belastbar, solange sich jede
  Einstufung auf eine benannte Regel zurückführen lässt.
- Keine externen Ressourcen. Keine CDN-Schriften, keine Fremdanfragen, kein
  Telemetriepfad. Siehe `SECURITY.md`; `tests/test_auslieferung.py` prüft es.
- Einstufungen werden historisiert, nie überschrieben.

Tests laufen mit `python -m pytest`. Neue Funktionen bekommen einen Test, der
die Aussage prüft und nicht die Formulierung.

---

## Vor dem Push

`PRE-PUSH.md` abarbeiten. Die Liste steht dort, obwohl `test_auslieferung.py`
das meiste abdeckt, weil ein Test nur prüft, woran jemand vorher gedacht hat.

Commit-Nachrichten auf Englisch, im Conventional-Commit-Stil, und sie
beschreiben, was sich fachlich geändert hat, nicht welche Zeilen bewegt wurden.
