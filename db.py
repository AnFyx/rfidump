"""Accès à la base SQLite locale : bacs (UID → établissement) et pesées notées.

Chaque fonction ouvre et ferme sa propre connexion : aucune connexion n'est
partagée entre threads (le poll RFID et Flask tournent sur des threads distincts).
Toutes les requêtes sont paramétrées (aucune concaténation de chaîne SQL).
"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from config import DB_PATH

# Jeu de bacs de démonstration inséré au premier lancement (UID → établissement)
_DEMO_BINS = [
    ("DEMO-UID-0001", "Cantine Lycée Jean Moulin"),
    ("DEMO-UID-0002", "Restaurant Le Gay-Lussac"),
    ("DEMO-UID-0003", "EHPAD Les Oliviers"),
]


def get_connection(db_path: Path = DB_PATH) -> sqlite3.Connection:
    """Ouvre une connexion SQLite avec lignes nommées et clés étrangères actives."""
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db(db_path: Path = DB_PATH) -> None:
    """Crée les tables si nécessaire et insère les bacs de démonstration."""
    with closing(get_connection(db_path)) as connection, connection:
        connection.executescript("""
            CREATE TABLE IF NOT EXISTS bins (
                uid           TEXT PRIMARY KEY,
                etablissement TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS weighings (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                uid           TEXT NOT NULL,
                etablissement TEXT NOT NULL,
                weight_kg     REAL NOT NULL,
                score         INTEGER NOT NULL CHECK (score BETWEEN 1 AND 3),
                photo_path    TEXT,
                created_at    TEXT NOT NULL
            );
            """)
        connection.executemany(
            "INSERT OR IGNORE INTO bins (uid, etablissement) VALUES (?, ?)",
            _DEMO_BINS,
        )


def lookup_bin(uid: str, db_path: Path = DB_PATH) -> Optional[str]:
    """Retourne l'établissement associé à un UID, ou None si le bac est inconnu."""
    with closing(get_connection(db_path)) as connection:
        row = connection.execute(
            "SELECT etablissement FROM bins WHERE uid = ?", (uid,)
        ).fetchone()
    return row["etablissement"] if row is not None else None


def record_weighing(
    uid: str,
    etablissement: str,
    weight_kg: float,
    score: int,
    photo_path: Optional[str],
    db_path: Path = DB_PATH,
) -> int:
    """Enregistre une pesée notée et retourne l'identifiant de la ligne créée."""
    created_at = datetime.now(timezone.utc).isoformat()
    with closing(get_connection(db_path)) as connection, connection:
        cursor = connection.execute(
            """
            INSERT INTO weighings
                (uid, etablissement, weight_kg, score, photo_path, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (uid, etablissement, weight_kg, score, photo_path, created_at),
        )
        return int(cursor.lastrowid)
