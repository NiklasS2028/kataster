# Verifikation der Fundstellen

Amtlicher Text: <https://eur-lex.europa.eu/eli/reg/2024/1689/oj?locale=de>

Nach Fundstelle gruppiert: Jede Normstelle muss nur einmal
aufgeschlagen werden. Innerhalb einer Gruppe von oben nach unten
abarbeiten, dann die IDs sammeln und in einem Aufruf setzen.

**Zu pruefen ist jeweils:** Stimmt die Fundstelle? Deckt sich die
Frageformulierung mit dem Normtext? Fehlt eine Tatbestandsvariante?
Ist eine genannte Ausnahme vollstaendig wiedergegeben?


## Art. 5

6 Regeln, davon 6 offen

- [ ] **V-01** &middot; `Art. 5 Abs. 1 lit. f KI-VO`  
      Wird das System eingesetzt, um Emotionen von Personen am Arbeitsplatz oder in Bildungseinrichtungen abzuleiten?  
      _Ausnahme im Entwurf:_ Gilt nicht, wenn die Verwendung aus medizinischen Gruenden oder Sicherheitsgruenden eingefuehrt oder in Verkehr gebracht werden soll.  
- [ ] **V-02** &middot; `Art. 5 Abs. 1 lit. g KI-VO`  
      Werden Personen anhand ihrer biometrischen Daten kategorisiert, um daraus Rasse, politische Einstellungen, Gewerkschaftszugehoerigkeit, religioese oder weltanschauliche Ueberzeugungen, das Sexualleben oder die sexuelle Ausrichtung abzuleiten?  
      _Ausnahme im Entwurf:_ Gilt nicht fuer die Kennzeichnung oder Filterung rechtmaessig erworbener biometrischer Datensaetze oder die Kategorisierung biometrischer Daten im Bereich der Strafverfolgung.  
- [ ] **V-03** &middot; `Art. 5 Abs. 1 lit. c KI-VO`  
      Werden Personen ueber einen Zeitraum anhand ihres sozialen Verhaltens oder persoenlicher Eigenschaften bewertet, und fuehrt diese Bewertung zu Benachteiligung in unzusammenhaengenden Kontexten oder zu unverhaeltnismaessiger Schlechterstellung?  
- [ ] **V-04** &middot; `Art. 5 Abs. 1 lit. e KI-VO`  
      Werden Gesichtsbilder ungezielt aus dem Internet oder aus Ueberwachungsaufnahmen ausgelesen, um Gesichtserkennungsdatenbanken zu erstellen oder zu erweitern?  
- [ ] **V-05** &middot; `Art. 5 Abs. 1 lit. a KI-VO`  
      Nutzt das System unterschwellige, manipulative oder taeuschende Techniken, um das Verhalten von Personen wesentlich zu veraendern, sodass ihnen oder anderen erheblicher Schaden zugefuegt wird?  
- [ ] **V-06** &middot; `Art. 5 Abs. 1 lit. b KI-VO`  
      Nutzt das System eine Schutzbeduerftigkeit aufgrund von Alter, Behinderung oder einer bestimmten sozialen oder wirtschaftlichen Situation aus, um Verhalten wesentlich zu veraendern und dadurch erheblichen Schaden zuzufuegen?  

```
python tools/verifizieren.py V-01 V-02 V-03 V-04 V-05 V-06 --von "NAME"
```

## Art. 50

5 Regeln, davon 5 offen

- [ ] **T-01** &middot; `Art. 50 Abs. 1 KI-VO`  
      Ist das System fuer die direkte Interaktion mit natuerlichen Personen bestimmt, etwa als Chatbot?  
      _Ausnahme im Entwurf:_ Entfaellt, wenn dies aus Sicht einer angemessen informierten, aufmerksamen und verstaendigen Person aufgrund der Umstaende offensichtlich ist.  
      _Hinweis:_ ANBIETERPFLICHT. Ein reiner Betreiber eines zugekauften Chatbots ist nicht Adressat. Er kann aber ueber R-02 zum Anbieter werden.  
- [ ] **T-05** &middot; `Art. 50 Abs. 2 KI-VO`  
      Erzeugt das System synthetische Audio-, Bild-, Video- oder Textinhalte?  
      _Ausnahme im Entwurf:_ Entfaellt, soweit das System eine unterstuetzende Funktion fuer die Standardbearbeitung ausfuehrt oder die Eingabedaten bzw. deren Semantik nicht wesentlich veraendert.  
      _Hinweis:_ ANBIETERPFLICHT.  
- [ ] **T-04** &middot; `Art. 50 Abs. 3 KI-VO`  
      Setzen Sie ein Emotionserkennungssystem oder ein System zur biometrischen Kategorisierung ein?  
      _Hinweis:_ BETREIBERPFLICHT.  
- [ ] **T-02** &middot; `Art. 50 Abs. 4 Unterabs. 1 KI-VO`  
      Erzeugen oder manipulieren Sie mit dem System Bild-, Ton- oder Videoinhalte, die wirklichen Personen, Orten oder Ereignissen aehneln und faelschlicherweise echt erscheinen wuerden (Deepfake)?  
      _Ausnahme im Entwurf:_ Bei offensichtlich kuenstlerischen, kreativen, satirischen oder fiktionalen Werken beschraenkt sich die Pflicht auf eine geeignete Offenlegung, die die Darstellung oder den Genuss des Werks nicht beeintraechtigt.  
      _Hinweis:_ BETREIBERPFLICHT.  
- [ ] **T-03** &middot; `Art. 50 Abs. 4 Unterabs. 2 KI-VO`  
      Veroeffentlichen Sie KI-erzeugte oder KI-manipulierte Texte, um die Oeffentlichkeit ueber Angelegenheiten von oeffentlichem Interesse zu informieren?  
      _Ausnahme im Entwurf:_ Entfaellt, wenn die Inhalte einer menschlichen Ueberpruefung oder redaktionellen Kontrolle unterzogen wurden und eine natuerliche oder juristische Person die redaktionelle Verantwortung traegt.  
      _Hinweis:_ BETREIBERPFLICHT.  

```
python tools/verifizieren.py T-01 T-05 T-04 T-02 T-03 --von "NAME"
```

## Anhang III

12 Regeln, davon 12 offen

- [ ] **H-07** &middot; `Anhang III Nr. 1 lit. a KI-VO`  
      Dient das System der biometrischen Fernidentifizierung von Personen?  
      _Ausnahme im Entwurf:_ Nicht erfasst sind Systeme zur biometrischen Verifizierung, deren einziger Zweck darin besteht, zu bestaetigen, dass eine Person die ist, fuer die sie sich ausgibt (z. B. Entsperren eines Geraets, Zugang zu einem Dienst).  
- [ ] **H-08** &middot; `Anhang III Nr. 1 lit. b KI-VO`  
      Dient das System der biometrischen Kategorisierung nach sensiblen oder geschuetzten Attributen, ohne unter das Verbot des Art. 5 zu fallen?  
- [ ] **H-09** &middot; `Anhang III Nr. 1 lit. c KI-VO`  
      Dient das System der Emotionserkennung ausserhalb von Arbeitsplatz und Bildungseinrichtungen, etwa im Kundenkontakt?  
      _Hinweis:_ Loest zusaetzlich die Transparenzpflicht T-04 nach Art. 50 Abs. 3 aus.  
- [ ] **H-06** &middot; `Anhang III Nr. 2 KI-VO`  
      Wird das System als Sicherheitsbauteil im Rahmen der Verwaltung oder des Betriebs kritischer digitaler Infrastruktur, des Strassenverkehrs oder der Wasser-, Gas-, Waerme- oder Stromversorgung eingesetzt?  
- [ ] **H-05** &middot; `Anhang III Nr. 3 KI-VO`  
      Steuert das System den Zugang oder die Zulassung zu Bildungseinrichtungen, bewertet es Lernergebnisse, bewertet es das angemessene Bildungsniveau einer Person oder ueberwacht es verbotenes Verhalten bei Pruefungen?  
- [ ] **H-01** &middot; `Anhang III Nr. 4 lit. a KI-VO`  
      Wird das System fuer die Einstellung oder Auswahl von Personen eingesetzt, insbesondere um gezielte Stellenanzeigen zu schalten, Bewerbungen zu sichten oder zu filtern oder Bewerber zu bewerten?  
- [ ] **H-02** &middot; `Anhang III Nr. 4 lit. b KI-VO`  
      Wird das System fuer Entscheidungen ueber Arbeitsbedingungen, Befoerderung oder Kuendigung, fuer die Zuweisung von Aufgaben anhand individuellen Verhaltens oder persoenlicher Merkmale, oder fuer die Beobachtung und Bewertung von Leistung und Verhalten Beschaeftigter eingesetzt?  
- [ ] **H-10** &middot; `Anhang III Nr. 5 lit. a KI-VO`  
      Wird das System von einer Behoerde oder in deren Namen verwendet, um ueber Anspruch, Gewaehrung, Einschraenkung, Widerruf oder Rueckforderung grundlegender oeffentlicher Unterstuetzungsleistungen zu entscheiden?  
- [ ] **H-03** &middot; `Anhang III Nr. 5 lit. b KI-VO`  
      Dient das System der Kreditwuerdigkeitspruefung oder Bonitaetsbewertung natuerlicher Personen?  
      _Ausnahme im Entwurf:_ Systeme zur Aufdeckung von Finanzbetrug sind ausgenommen.  
- [ ] **H-04** &middot; `Anhang III Nr. 5 lit. c KI-VO`  
      Dient das System der Risikobewertung oder Preisbildung in Bezug auf natuerliche Personen bei Lebens- oder Krankenversicherungen?  
- [ ] **H-11** &middot; `Anhang III Nr. 5 lit. d KI-VO`  
      Dient das System der Bewertung und Klassifizierung von Notrufen, der Entsendung oder Priorisierung von Not- und Rettungsdiensten oder der Triage von Patienten in der Notfallversorgung?  
- [ ] **H-12** &middot; `Anhang III Nr. 8 lit. a KI-VO`  
      Wird das System eingesetzt, um bei der Ermittlung und Auslegung von Sachverhalten und Rechtsvorschriften zu unterstuetzen - etwa im Rahmen alternativer Streitbeilegung mit Rechtswirkung fuer die Parteien?  
      _Hinweis:_ Betrifft Justizbehoerden sowie Stellen fuer alternative Streitbeilegung. Reine Verwaltungstaetigkeiten wie Anonymisierung sind nicht erfasst.  

```
python tools/verifizieren.py H-07 H-08 H-09 H-06 H-05 H-01 H-02 H-10 H-03 H-04 H-11 H-12 --von "NAME"
```

## Art. 6

1 Regeln, davon 1 offen

- [ ] **P-01** &middot; `Art. 6 Abs. 1 KI-VO i. V. m. Anhang I`  
      Ist das KI-System ein Sicherheitsbauteil eines Produkts, das unter die Harmonisierungsrechtsvorschriften aus Anhang I faellt (u. a. Maschinen, Spielzeug, Aufzuege, Druckgeraete, Funkanlagen, Seilbahnen, persoenliche Schutzausruestung, Medizinprodukte, In-vitro-Diagnostika, Fahrzeuge, Luftfahrzeuge) - oder ist es selbst ein solches Produkt?  
      _Hinweis:_ Beide Bedingungen muessen kumulativ erfuellt sein. Der Ausnahmefilter des Art. 6 Abs. 3 gilt fuer diesen Pfad NICHT - er bezieht sich nur auf Anhang III.  

```
python tools/verifizieren.py P-01 --von "NAME"
```

---

Offen: 24 von 24.

Solange nicht alle Regeln verifiziert sind, meldet
`Regelwerk.ausspielbar()` falsch, die Fusszeile weist auf den
Entwurfsstand hin, und das Nachweis-Dossier traegt einen Warnkasten.
