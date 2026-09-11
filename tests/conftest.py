"""Configuration commune des tests : base temporaire et mode simulation.

Les variables d'environnement doivent être posées AVANT l'import de `config`,
qui les lit une seule fois : c'est pourquoi elles sont définies ici, au chargement.
"""

from __future__ import annotations

import os
import sqlite3
import tempfile
from pathlib import Path
from typing import Iterator

import pytest

_TEST_DIR = Path(tempfile.mkdtemp(prefix="rfidump-tests-"))
os.environ["STATION_DB_PATH"] = str(_TEST_DIR / "station-test.db")
os.environ["STATION_HW"] = "sim"


@pytest.fixture
def fresh_db() -> Iterator[Path]:
    """Base de test initialisée, vidée de ses pesées avant chaque test."""
    import db
    from config import DB_PATH

    db.init_db()
    connection = sqlite3.connect(DB_PATH)
    try:
        with connection:
            connection.execute("DELETE FROM weighings")
    finally:
        connection.close()
    yield DB_PATH


def fetch_weighings(db_path: Path) -> list[tuple]:
    """Retourne (uid, weight_kg, score, photo_path) pour chaque pesée enregistrée."""
    connection = sqlite3.connect(db_path)
    try:
        return connection.execute(
            "SELECT uid, weight_kg, score, photo_path FROM weighings ORDER BY id"
        ).fetchall()
    finally:
        connection.close()
