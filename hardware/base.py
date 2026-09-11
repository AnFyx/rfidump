"""Interfaces matérielles abstraites du poste.

Le reste du code ne dépend que de ces interfaces. Deux implémentations existent :
- simulator.py : sans matériel (développement sur PC) ;
- real.py : Raspberry Pi câblé (RC522, GPIO, caméra, banc de pesée).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Callable, Optional


class RfidReader(ABC):
    """Lecteur RFID : fournit l'UID du tag présenté."""

    @abstractmethod
    def read_uid(self) -> Optional[str]:
        """Retourne l'UID lu, ou None si aucun tag présent.

        Implémentation non bloquante : appelée en boucle de scrutation.
        """


class Scale(ABC):
    """Balance : fournit le poids courant sur le banc de pesée."""

    @abstractmethod
    def read_weight_kg(self) -> float:
        """Retourne le poids mesuré, en kilogrammes."""


class Camera(ABC):
    """Caméra de justification : capture une photo du contenu du bac."""

    @abstractmethod
    def capture(self, destination_dir: Path) -> str:
        """Capture une image, l'enregistre, et retourne son chemin web relatif."""


class ButtonPanel(ABC):
    """Panneau de boutons physiques (notes étoiles + déclenchement photo)."""

    @abstractmethod
    def start(
        self,
        on_score: Callable[[int], None],
        on_photo: Callable[[], None],
    ) -> None:
        """Démarre l'écoute des boutons et câble les callbacks métier."""

    @abstractmethod
    def stop(self) -> None:
        """Arrête l'écoute et libère les ressources matérielles."""
