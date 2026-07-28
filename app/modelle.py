"""
modelle.py - Datenhaltung fuer Kataster.

Bewusst ohne ORM: sqlite3 aus der Standardbibliothek reicht fuer ein
Einzelplatzwerkzeug und haelt die Abhaengigkeitsliste kurz.

Zwei Grundsaetze, die das Schema traegt:

1. Einstufungen werden HISTORISIERT, nie ueberschrieben. Wenn sich das
   Regelwerk aendert, muss nachvollziehbar bleiben, was zu welchem Zeitpunkt
   galt. Genau das macht ein Nachweis-Dossier belastbar.
2. Jede Einstufung traegt Regelwerksversion, Rechtsstand und den Hash der
   Regelwerksdatei. Ohne diese drei Angaben ist ein Nachweis wertlos.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator

SCHEMA_VERSION = 2

# Vokabular fuer das Feld datenkategorien. Bewusst hier und nicht im Regelwerk:
# Das sind Begriffe der Erfassung, kein Rechtsinhalt.
DATENKATEGORIEN = [
    ("personenbezogen", "Personenbezogene Daten"),
    ("besondere_kategorien", "Besondere Kategorien (Gesundheit, Herkunft, Religion \u2026)"),
    ("beschaeftigtendaten", "Daten von Beschaeftigten"),
    ("kundendaten", "Kundendaten"),
    ("geschaeftsgeheimnisse", "Geschaeftsgeheimnisse, Kalkulationen, Quellcode"),
    ("keine", "Keine der genannten"),
]

STATUS = [
    ("in_pruefung", "In Pruefung"),
    ("freigegeben", "Freigegeben"),
    ("geduldet", "Geduldet"),
    ("untersagt", "Untersagt"),
]

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_info (
    version     INTEGER NOT NULL,
    angelegt_am TEXT    NOT NULL
);

-- Stammdaten des Unternehmens. Genau eine Zeile.
CREATE TABLE IF NOT EXISTS organisation (
    id                  INTEGER PRIMARY KEY CHECK (id = 1),
    name                TEXT,
    rechtsform          TEXT,
    beschaeftigte       INTEGER,
    ist_behoerde        INTEGER NOT NULL DEFAULT 0,
    erbringt_oeff_dienste INTEGER NOT NULL DEFAULT 0,
    ansprechpartner     TEXT,
    -- Selbstauskunft nach Empfehlung 2003/361/EG bzw. (EU) 2025/1099.
    -- Kataster berechnet die Klasse nicht, es uebernimmt die Angabe.
    groessenklasse      TEXT,
    hat_partner_oder_verbund INTEGER NOT NULL DEFAULT 0,
    geaendert_am        TEXT
);

CREATE TABLE IF NOT EXISTS system (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    name                    TEXT NOT NULL,
    anbieter                TEXT,
    url                     TEXT,
    zweck                   TEXT,
    abteilung               TEXT,
    verantwortlich          TEXT,
    rolle                   TEXT NOT NULL DEFAULT 'betreiber'
                            CHECK (rolle IN ('betreiber','anbieter','beides')),
    status                  TEXT NOT NULL DEFAULT 'in_pruefung'
                            CHECK (status IN ('freigegeben','geduldet','untersagt','in_pruefung')),
    quelle                  TEXT NOT NULL DEFAULT 'offiziell'
                            CHECK (quelle IN ('offiziell','schatten_gemeldet')),
    -- Art. 111 Abs. 2: Bestandsschutz
    in_betrieb_seit         TEXT,
    wesentlich_veraendert_am TEXT,
    -- Kostentransparenz
    kosten_monat_eur        REAL,
    kostenstelle            TEXT,
    -- Datenschutzrelevante Merkmale
    av_vertrag              INTEGER NOT NULL DEFAULT 0,
    eu_hosting              INTEGER NOT NULL DEFAULT 0,
    training_mit_eingaben   INTEGER NOT NULL DEFAULT 0,
    datenkategorien         TEXT NOT NULL DEFAULT '[]',
    notiz                   TEXT,
    erstellt_am             TEXT NOT NULL,
    geaendert_am            TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS flag (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    system_id     INTEGER NOT NULL REFERENCES system(id) ON DELETE CASCADE,
    flag_name     TEXT    NOT NULL,
    antwort       INTEGER NOT NULL CHECK (antwort IN (0,1)),
    beantwortet_am TEXT   NOT NULL,
    beantwortet_von TEXT,
    UNIQUE (system_id, flag_name)
);

CREATE TABLE IF NOT EXISTS einstufung (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    system_id           INTEGER NOT NULL REFERENCES system(id) ON DELETE CASCADE,
    klasse              TEXT    NOT NULL,
    rang                INTEGER NOT NULL,
    lesart              TEXT    NOT NULL,
    rolle               TEXT    NOT NULL,
    regelwerk_version   TEXT    NOT NULL,
    rechtsstand         TEXT    NOT NULL,
    regelwerk_hash      TEXT    NOT NULL,
    ausgeloest_durch    TEXT    NOT NULL DEFAULT '[]',
    ergebnis_json       TEXT    NOT NULL,
    bestandsschutz_greift INTEGER NOT NULL DEFAULT 0,
    berechnet_am        TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_einstufung_system
    ON einstufung(system_id, berechnet_am DESC);

-- Dokumentierte Entscheidung nach Art. 6 Abs. 3 und 4.
-- Wird nie automatisch gesetzt, immer nur vom Nutzer mit Begruendung.
CREATE TABLE IF NOT EXISTS ausnahmeentscheidung (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    system_id     INTEGER NOT NULL REFERENCES system(id) ON DELETE CASCADE,
    bedingung_id  TEXT    NOT NULL,
    begruendung   TEXT    NOT NULL,
    entschieden_von TEXT,
    entschieden_am TEXT   NOT NULL
);

CREATE TABLE IF NOT EXISTS nachweis (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    typ               TEXT NOT NULL
                      CHECK (typ IN ('richtlinie','schulung','dossier','inventar')),
    dateiname         TEXT NOT NULL,
    regelwerk_version TEXT NOT NULL,
    rechtsstand       TEXT NOT NULL,
    hash_sha256       TEXT NOT NULL,
    erzeugt_am        TEXT NOT NULL
);
"""


def _jetzt() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


# ---------------------------------------------------------------------------
# Verbindung
# ---------------------------------------------------------------------------


class Datenbank:
    def __init__(self, pfad: str | Path = "kataster.sqlite"):
        self.pfad = Path(pfad)
        self._init_schema()

    @contextmanager
    def verbindung(self) -> Iterator[sqlite3.Connection]:
        con = sqlite3.connect(self.pfad)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys = ON")
        try:
            yield con
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()

    def _init_schema(self) -> None:
        with self.verbindung() as con:
            con.executescript(SCHEMA)
            vorhanden = con.execute("SELECT COUNT(*) FROM schema_info").fetchone()[0]
            if not vorhanden:
                con.execute(
                    "INSERT INTO schema_info (version, angelegt_am) VALUES (?, ?)",
                    (SCHEMA_VERSION, _jetzt()),
                )
            else:
                self._migrieren(con)
            con.execute(
                "INSERT OR IGNORE INTO organisation (id, geaendert_am) VALUES (1, ?)",
                (_jetzt(),),
            )

    def _migrieren(self, con: sqlite3.Connection) -> None:
        """Hebt eine bestehende Datenbank auf SCHEMA_VERSION.

        CREATE TABLE IF NOT EXISTS legt fehlende Tabellen an, ergaenzt aber
        keine Spalten in bereits bestehenden. Neue Spalten muessen deshalb per
        ALTER TABLE nachgezogen werden, sonst fehlen sie in Altbestaenden. Die
        Version wird als neue Zeile fortgeschrieben, nicht ueberschrieben.
        """
        version = con.execute("SELECT MAX(version) FROM schema_info").fetchone()[0] or 0
        if version < 2:
            # v1 -> v2: Groessenklasse als Organisationsattribut (Phase 7).
            con.execute("ALTER TABLE organisation ADD COLUMN groessenklasse TEXT")
            con.execute(
                "ALTER TABLE organisation "
                "ADD COLUMN hat_partner_oder_verbund INTEGER NOT NULL DEFAULT 0"
            )
        if version < SCHEMA_VERSION:
            con.execute(
                "INSERT INTO schema_info (version, angelegt_am) VALUES (?, ?)",
                (SCHEMA_VERSION, _jetzt()),
            )

    # -- Organisation --------------------------------------------------------

    def organisation_lesen(self) -> dict[str, Any]:
        with self.verbindung() as con:
            zeile = con.execute("SELECT * FROM organisation WHERE id = 1").fetchone()
            return dict(zeile) if zeile else {}

    def organisation_speichern(self, **felder: Any) -> None:
        erlaubt = {
            "name", "rechtsform", "beschaeftigte", "ist_behoerde",
            "erbringt_oeff_dienste", "ansprechpartner",
            "groessenklasse", "hat_partner_oder_verbund",
        }
        daten = {k: v for k, v in felder.items() if k in erlaubt}
        if not daten:
            return
        daten["geaendert_am"] = _jetzt()
        zuweisung = ", ".join(f"{k} = ?" for k in daten)
        with self.verbindung() as con:
            con.execute(
                f"UPDATE organisation SET {zuweisung} WHERE id = 1",
                list(daten.values()),
            )

    # -- Systeme -------------------------------------------------------------

    def system_anlegen(self, name: str, **felder: Any) -> int:
        felder["name"] = name
        felder.setdefault("datenkategorien", [])
        if isinstance(felder["datenkategorien"], (list, tuple)):
            felder["datenkategorien"] = json.dumps(
                list(felder["datenkategorien"]), ensure_ascii=False
            )
        jetzt = _jetzt()
        felder["erstellt_am"] = jetzt
        felder["geaendert_am"] = jetzt

        spalten = ", ".join(felder)
        platzhalter = ", ".join("?" for _ in felder)
        with self.verbindung() as con:
            cur = con.execute(
                f"INSERT INTO system ({spalten}) VALUES ({platzhalter})",
                list(felder.values()),
            )
            return int(cur.lastrowid)

    def system_lesen(self, system_id: int) -> dict[str, Any] | None:
        with self.verbindung() as con:
            zeile = con.execute(
                "SELECT * FROM system WHERE id = ?", (system_id,)
            ).fetchone()
            if not zeile:
                return None
            daten = dict(zeile)
            daten["datenkategorien"] = json.loads(daten["datenkategorien"])
            return daten

    def system_aktualisieren(self, system_id: int, **felder: Any) -> None:
        if "datenkategorien" in felder and isinstance(
            felder["datenkategorien"], (list, tuple)
        ):
            felder["datenkategorien"] = json.dumps(
                list(felder["datenkategorien"]), ensure_ascii=False
            )
        felder["geaendert_am"] = _jetzt()
        zuweisung = ", ".join(f"{k} = ?" for k in felder)
        with self.verbindung() as con:
            con.execute(
                f"UPDATE system SET {zuweisung} WHERE id = ?",
                list(felder.values()) + [system_id],
            )

    def systeme_auflisten(self, quelle: str | None = None) -> list[dict[str, Any]]:
        sql = "SELECT * FROM system"
        parameter: list[Any] = []
        if quelle:
            sql += " WHERE quelle = ?"
            parameter.append(quelle)
        sql += " ORDER BY name COLLATE NOCASE"
        with self.verbindung() as con:
            zeilen = con.execute(sql, parameter).fetchall()
        ergebnis = []
        for z in zeilen:
            d = dict(z)
            d["datenkategorien"] = json.loads(d["datenkategorien"])
            ergebnis.append(d)
        return ergebnis

    def system_loeschen(self, system_id: int) -> None:
        with self.verbindung() as con:
            con.execute("DELETE FROM system WHERE id = ?", (system_id,))

    # -- Flags ---------------------------------------------------------------

    def flag_setzen(
        self,
        system_id: int,
        flag_name: str,
        antwort: bool,
        beantwortet_von: str | None = None,
    ) -> None:
        with self.verbindung() as con:
            con.execute(
                """
                INSERT INTO flag (system_id, flag_name, antwort, beantwortet_am, beantwortet_von)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT (system_id, flag_name) DO UPDATE SET
                    antwort = excluded.antwort,
                    beantwortet_am = excluded.beantwortet_am,
                    beantwortet_von = excluded.beantwortet_von
                """,
                (system_id, flag_name, int(antwort), _jetzt(), beantwortet_von),
            )

    def flags_lesen(self, system_id: int) -> dict[str, bool]:
        with self.verbindung() as con:
            zeilen = con.execute(
                "SELECT flag_name, antwort FROM flag WHERE system_id = ?",
                (system_id,),
            ).fetchall()
        return {z["flag_name"]: bool(z["antwort"]) for z in zeilen}

    # -- Einstufungen --------------------------------------------------------

    def einstufung_speichern(self, system_id: int, ergebnis: dict[str, Any]) -> int:
        """Legt IMMER einen neuen Datensatz an. Historie bleibt vollstaendig."""
        with self.verbindung() as con:
            cur = con.execute(
                """
                INSERT INTO einstufung (
                    system_id, klasse, rang, lesart, rolle,
                    regelwerk_version, rechtsstand, regelwerk_hash,
                    ausgeloest_durch, ergebnis_json,
                    bestandsschutz_greift, berechnet_am
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    system_id,
                    ergebnis["klasse"],
                    ergebnis["rang"],
                    ergebnis["lesart"],
                    ergebnis["rolle"],
                    ergebnis["regelwerk_version"],
                    ergebnis["rechtsstand"],
                    ergebnis["regelwerk_hash"],
                    json.dumps(ergebnis["ausgeloest_durch"], ensure_ascii=False),
                    json.dumps(ergebnis, ensure_ascii=False),
                    int(bool(ergebnis.get("bestandsschutz_greift"))),
                    ergebnis["berechnet_am"],
                ),
            )
            return int(cur.lastrowid)

    def einstufung_aktuell(
        self, system_id: int, lesart: str | None = None
    ) -> dict[str, Any] | None:
        sql = "SELECT * FROM einstufung WHERE system_id = ?"
        parameter: list[Any] = [system_id]
        if lesart:
            sql += " AND lesart = ?"
            parameter.append(lesart)
        sql += " ORDER BY berechnet_am DESC, id DESC LIMIT 1"
        with self.verbindung() as con:
            zeile = con.execute(sql, parameter).fetchone()
        if not zeile:
            return None
        daten = dict(zeile)
        daten["ergebnis"] = json.loads(daten.pop("ergebnis_json"))
        daten["ausgeloest_durch"] = json.loads(daten["ausgeloest_durch"])
        return daten

    def einstufung_historie(self, system_id: int) -> list[dict[str, Any]]:
        with self.verbindung() as con:
            zeilen = con.execute(
                """
                SELECT id, klasse, lesart, regelwerk_version, rechtsstand,
                       regelwerk_hash, berechnet_am
                FROM einstufung WHERE system_id = ?
                ORDER BY berechnet_am DESC, id DESC
                """,
                (system_id,),
            ).fetchall()
        return [dict(z) for z in zeilen]

    # -- Ausnahmeentscheidungen ---------------------------------------------

    def ausnahme_dokumentieren(
        self,
        system_id: int,
        bedingung_id: str,
        begruendung: str,
        entschieden_von: str | None = None,
    ) -> int:
        if not begruendung.strip():
            raise ValueError(
                "Eine Ausnahme nach Art. 6 Abs. 3 ist ohne Begruendung wertlos."
            )
        with self.verbindung() as con:
            cur = con.execute(
                """
                INSERT INTO ausnahmeentscheidung
                    (system_id, bedingung_id, begruendung, entschieden_von, entschieden_am)
                VALUES (?,?,?,?,?)
                """,
                (system_id, bedingung_id, begruendung, entschieden_von, _jetzt()),
            )
            return int(cur.lastrowid)

    def ausnahmen_lesen(self, system_id: int) -> list[dict[str, Any]]:
        with self.verbindung() as con:
            zeilen = con.execute(
                "SELECT * FROM ausnahmeentscheidung WHERE system_id = ? ORDER BY entschieden_am DESC",
                (system_id,),
            ).fetchall()
        return [dict(z) for z in zeilen]

    # -- Nachweise -----------------------------------------------------------

    def nachweis_erfassen(
        self,
        typ: str,
        dateiname: str,
        regelwerk_version: str,
        rechtsstand: str,
        hash_sha256: str,
    ) -> int:
        with self.verbindung() as con:
            cur = con.execute(
                """
                INSERT INTO nachweis
                    (typ, dateiname, regelwerk_version, rechtsstand, hash_sha256, erzeugt_am)
                VALUES (?,?,?,?,?,?)
                """,
                (typ, dateiname, regelwerk_version, rechtsstand, hash_sha256, _jetzt()),
            )
            return int(cur.lastrowid)

    def nachweise_auflisten(self) -> list[dict[str, Any]]:
        with self.verbindung() as con:
            zeilen = con.execute(
                "SELECT * FROM nachweis ORDER BY erzeugt_am DESC"
            ).fetchall()
        return [dict(z) for z in zeilen]

    # -- Auswertung ----------------------------------------------------------

    def kennzahlen(self) -> dict[str, Any]:
        """Grundlage fuer die Uebersichtsseite und das Dossier-Deckblatt."""
        with self.verbindung() as con:
            gesamt = con.execute("SELECT COUNT(*) FROM system").fetchone()[0]
            nach_quelle = dict(
                con.execute(
                    "SELECT quelle, COUNT(*) FROM system GROUP BY quelle"
                ).fetchall()
            )
            nach_status = dict(
                con.execute(
                    "SELECT status, COUNT(*) FROM system GROUP BY status"
                ).fetchall()
            )
            kosten = con.execute(
                "SELECT COALESCE(SUM(kosten_monat_eur), 0) FROM system"
            ).fetchone()[0]
            nach_klasse = dict(
                con.execute(
                    """
                    SELECT e.klasse, COUNT(*) FROM einstufung e
                    JOIN (
                        SELECT system_id, MAX(id) AS max_id
                        FROM einstufung GROUP BY system_id
                    ) neueste ON e.id = neueste.max_id
                    GROUP BY e.klasse
                    """
                ).fetchall()
            )
            ohne_einstufung = con.execute(
                "SELECT COUNT(*) FROM system s "
                "WHERE NOT EXISTS (SELECT 1 FROM einstufung e WHERE e.system_id = s.id)"
            ).fetchone()[0]

        return {
            "systeme_gesamt": gesamt,
            "nach_quelle": nach_quelle,
            "nach_status": nach_status,
            "nach_klasse": nach_klasse,
            "ohne_einstufung": ohne_einstufung,
            "kosten_monat_eur": round(float(kosten), 2),
            "kosten_jahr_eur": round(float(kosten) * 12, 2),
        }


if __name__ == "__main__":
    db = Datenbank(":memory:")
    print("Schema angelegt. Tabellen:")
    with db.verbindung() as con:
        for z in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ):
            print("  -", z["name"])
