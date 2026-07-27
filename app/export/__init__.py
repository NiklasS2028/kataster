"""
Erzeugung der Nachweise.

Vier Ausgaben, alle lokal in den Ordner exporte/:

  inventar.csv      Bestandsverzeichnis fuer Tabellenkalkulation
  ki-richtlinie.md  Entwurf einer KI-Richtlinie, zum Weiterbearbeiten
  schulungsmatrix.md  Wer braucht welche Inhalte
  dossier.html      Nachweis-Dossier, im Browser druckbar

Jede erzeugte Datei wird gehasht und in der Tabelle nachweis vermerkt. Der
Nachweis haengt am erzeugten Dokument, nicht am spaeteren Ausdruck.
"""

from .schreiber import erzeuge_alle, EXPORTORDNER

__all__ = ["erzeuge_alle", "EXPORTORDNER"]
