"""Configuration centrale du poste RFID (chemins, constantes, mode matériel)."""

from __future__ import annotations

import os
from pathlib import Path

# Répertoire racine du projet
BASE_DIR = Path(__file__).resolve().parent

# Base de données SQLite locale (UID des bacs + historique des pesées).
# Surchargeable par STATION_DB_PATH (tests, ou base hors du dossier du code).
DB_PATH = Path(os.environ.get("STATION_DB_PATH", BASE_DIR / "station.db"))

# Répertoire de stockage des photos de justification
PHOTO_DIR = BASE_DIR / "static" / "photos"

# Image de substitution renvoyée en mode simulateur (chemin web relatif à /static)
PLACEHOLDER_PHOTO = "photos/placeholder.svg"

# Mode matériel : "sim" (défaut, sans câbles) ou "real" (Raspberry Pi câblé).
# Surchargeable par la variable d'environnement STATION_HW.
HARDWARE_MODE = os.environ.get("STATION_HW", "sim")

# Bornes de la note qualité, en étoiles
MIN_SCORE = 1
MAX_SCORE = 3

# Période de scrutation du lecteur RFID (secondes)
RFID_POLL_INTERVAL_S = 0.2

# Un tag resté sur le banc est relu à chaque scrutation. Tant qu'il est revu dans
# ce délai, il s'agit de la même présentation (pas de nouveau cycle de pesée) ;
# il faut le retirer au moins ce temps pour démarrer un nouveau cycle (secondes).
RESCAN_GRACE_PERIOD_S = 2.0

# Intervalle d'envoi du heartbeat SSE pour maintenir la connexion ouverte (secondes)
SSE_HEARTBEAT_INTERVAL = 15.0

# Taille max de la file d'événements par client SSE (borne anti-saturation mémoire)
SSE_QUEUE_MAXSIZE = 100

# Nombre max de clients SSE simultanés : chaque client occupe un thread du serveur
# pendant toute sa connexion ; sans borne, ouvrir des connexions épuise le serveur.
SSE_MAX_CLIENTS = 10

# Longueur max d'un UID accepté par l'endpoint de simulation
MAX_UID_LENGTH = 64

# Interface d'écoute du serveur. Par défaut, la machine locale uniquement :
# l'exposition au réseau doit être un choix explicite. Sur le Pi, pour afficher
# la page depuis un autre poste du LAN : STATION_HOST=0.0.0.0 (réseau de confiance
# uniquement, voir la section sécurité du README).
HOST = os.environ.get("STATION_HOST", "127.0.0.1")

# Port d'écoute, surchargeable par STATION_PORT.
_DEFAULT_PORT = 8000
_MIN_PORT = 1
_MAX_PORT = 65535


def _read_port(raw_value: str) -> int:
    """Convertit STATION_PORT en entier valide, ou échoue fermé au démarrage."""
    try:
        port = int(raw_value)
    except ValueError as exc:
        raise ValueError(f"STATION_PORT invalide : {raw_value!r}") from exc
    if not _MIN_PORT <= port <= _MAX_PORT:
        raise ValueError(f"STATION_PORT hors bornes : {port}")
    return port


PORT = _read_port(os.environ.get("STATION_PORT", str(_DEFAULT_PORT)))
