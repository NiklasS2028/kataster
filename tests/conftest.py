"""Gemeinsame Vorrichtungen fuer die Testsuite."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL))

REGELWERK_PFAD = WURZEL / "rules" / "ai-act_2026-07-23.yaml"


@pytest.fixture(scope="session")
def regelwerk():
    from app.regelwerk import Regelwerk
    return Regelwerk.laden(REGELWERK_PFAD)


@pytest.fixture
def datenbank(tmp_path):
    from app.modelle import Datenbank
    return Datenbank(tmp_path / "test.sqlite")


@pytest.fixture
def app(tmp_path):
    from app import erzeuge_app
    anwendung = erzeuge_app({
        "DATENBANK_PFAD": str(tmp_path / "test.sqlite"),
        "REGELWERK_PFAD": str(REGELWERK_PFAD),
        "SECRET_KEY": "test",
        "TESTING": True,
        "WTF_CSRF_ENABLED": False,
    })
    return anwendung


@pytest.fixture
def klient(app):
    return app.test_client()


@pytest.fixture
def arbeitsordner(tmp_path):
    return tmp_path
