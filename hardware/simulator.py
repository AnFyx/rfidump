"""Implémentations simulées du matériel, pour développer sans le Pi ni les câbles.

Aucune de ces classes ne touche au matériel : les « événements » (présentation
d'un bac, appui sur un bouton) sont injectés depuis l'UI web de simulation.
L'aléa utilisé ici est purement cosmétique (poids de démo) — sans enjeu de sécurité.
"""

from __future__ import annotations

import logging
import random
import threading
from pathlib import Path
from typing import Callable, Optional

from config import PLACEHOLDER_PHOTO
from hardware.base import ButtonPanel, Camera, RfidReader, Scale

logger = logging.getLogger(__name__)

# Plage de poids simulée, plausible pour un bac de biodéchets (kg)
_SIM_WEIGHT_MIN_KG = 8.0
_SIM_WEIGHT_MAX_KG = 45.0


class SimulatedRfidReader(RfidReader):
    """Lecteur simulé : un UID injecté est renvoyé une seule fois, puis None."""

    def __init__(self) -> None:
        self._pending_uid: Optional[str] = None
        self._lock = threading.Lock()

    def present_tag(self, uid: str) -> None:
        """Injecte un UID comme si un tag venait d'être présenté (commande de simu)."""
        with self._lock:
            self._pending_uid = uid

    def read_uid(self) -> Optional[str]:
        """Consomme l'UID injecté (une fois), sinon None."""
        with self._lock:
            uid = self._pending_uid
            self._pending_uid = None
        return uid


class SimulatedScale(Scale):
    """Balance simulée : poids pseudo-aléatoire, stable entre deux présentations."""

    def __init__(self) -> None:
        self._current_kg = 0.0

    def new_load(self) -> None:
        """Tire un nouveau poids ; à appeler quand un bac est présenté."""
        self._current_kg = round(
            random.uniform(_SIM_WEIGHT_MIN_KG, _SIM_WEIGHT_MAX_KG), 1
        )

    def read_weight_kg(self) -> float:
        """Retourne le poids simulé courant."""
        return self._current_kg


class SimulatedCamera(Camera):
    """Caméra simulée : ne capture rien, renvoie l'image de substitution."""

    def capture(self, destination_dir: Path) -> str:
        """Ignore la destination et renvoie le chemin web de l'image de substitution."""
        logger.info("Capture simulée : image de substitution renvoyée")
        return PLACEHOLDER_PHOTO


class SimulatedButtonPanel(ButtonPanel):
    """Panneau simulé : les appuis proviennent de l'UI web, pas du GPIO."""

    def __init__(self) -> None:
        self._on_score: Optional[Callable[[int], None]] = None
        self._on_photo: Optional[Callable[[], None]] = None

    def start(
        self,
        on_score: Callable[[int], None],
        on_photo: Callable[[], None],
    ) -> None:
        """Mémorise les callbacks ; déclenchés via les routes /sim/*."""
        self._on_score = on_score
        self._on_photo = on_photo

    def stop(self) -> None:
        """Rien à libérer en simulation."""
        self._on_score = None
        self._on_photo = None

    def press_score(self, value: int) -> None:
        """Simule un appui sur un bouton étoile."""
        if self._on_score is not None:
            self._on_score(value)

    def press_photo(self) -> None:
        """Simule un appui sur le bouton photo."""
        if self._on_photo is not None:
            self._on_photo()
