"""Configuration centrale du poste RFID (chemins, constantes, mode matériel)."""

from __future__ import annotations

import os
from pathlib import Path

# Répertoire racine du projet
BASE_DIR = Path(__file__).resolve().parent

# Base de données SQLite locale (UID des bacs + historique des pesées)
DB_PATH = BASE_DIR / "station.db"

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

# Intervalle d'envoi du heartbeat SSE pour maintenir la connexion ouverte (secondes)
SSE_HEARTBEAT_INTERVAL = 15.0

# Taille max de la file d'événements par client SSE (borne anti-saturation mémoire)
SSE_QUEUE_MAXSIZE = 100

# Interface et port d'écoute du serveur.
# 0.0.0.0 = écoute sur toutes les interfaces, nécessaire pour joindre le Pi
# depuis le PC sur le LAN. Voir les notes de sécurité du README (réseau de confiance).
HOST = "0.0.0.0"
PORT = 8000
