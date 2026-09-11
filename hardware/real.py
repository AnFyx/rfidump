"""Implémentations matérielles réelles : RC522, boutons GPIO, caméra, banc de pesée.

À n'importer que sur le Raspberry Pi, une fois le câblage en place : ce module
dépend de `mfrc522` et `gpiozero`, absents/inutilisables sur un PC. La fabrique
(`hardware/__init__.py`) ne l'importe qu'en mode "real".

Statut : le lecteur RC522 et les boutons GPIO sont écrits ; la caméra et le banc
de pesée sont des points d'extension à compléter quand le matériel sera branché
(voir les NotImplementedError). Le câblage RC522/boutons est documenté dans le README.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable, List, Optional

from hardware.base import ButtonPanel, Camera, RfidReader, Scale

logger = logging.getLogger(__name__)

# Correspondance bouton étoile → broche GPIO (numérotation BCM). Voir README.
_PIN_SCORE = {1: 5, 2: 6, 3: 13}
# Broche du bouton « prendre la photo »
_PIN_PHOTO = 19
# Anti-rebond logiciel des boutons (secondes)
_BUTTON_BOUNCE_TIME_S = 0.1


class Rc522Reader(RfidReader):
    """Lecteur réel basé sur le module MFRC522 (bus SPI)."""

    def __init__(self) -> None:
        # Import localisé : la lib n'est chargée que sur le Pi.
        from mfrc522 import MFRC522

        self._reader = MFRC522()

    def read_uid(self) -> Optional[str]:
        """Scrute le lecteur une fois et renvoie l'UID en hexa, ou None.

        Non bloquant : on utilise l'API bas niveau (Request + Anticoll) plutôt
        que SimpleMFRC522.read(), qui bloque jusqu'à détection d'un tag.
        Les noms d'attributs/constantes sont ceux de la lib `mfrc522` ; à
        confirmer sur le matériel lors du premier test de lecture.
        """
        reader = self._reader
        status, _ = reader.MFRC522_Request(reader.PICC_REQIDL)
        if status != reader.MI_OK:
            return None
        status, uid_bytes = reader.MFRC522_Anticoll()
        if status != reader.MI_OK:
            return None
        return "".join(f"{byte:02X}" for byte in uid_bytes)


class GpioButtonPanel(ButtonPanel):
    """Boutons poussoirs réels câblés sur le GPIO via gpiozero (pull-up interne)."""

    def __init__(self) -> None:
        self._buttons: List[object] = []

    def start(
        self,
        on_score: Callable[[int], None],
        on_photo: Callable[[], None],
    ) -> None:
        """Crée les objets Button et câble leurs callbacks d'appui."""
        from gpiozero import Button

        for value, pin in _PIN_SCORE.items():
            button = Button(pin, pull_up=True, bounce_time=_BUTTON_BOUNCE_TIME_S)
            # `value=value` fige la valeur : sans ça, la closure capturerait la
            # dernière valeur de la boucle (piège classique de fermeture tardive).
            button.when_pressed = lambda value=value: on_score(value)
            self._buttons.append(button)

        photo_button = Button(
            _PIN_PHOTO, pull_up=True, bounce_time=_BUTTON_BOUNCE_TIME_S
        )
        photo_button.when_pressed = lambda: on_photo()
        self._buttons.append(photo_button)

    def stop(self) -> None:
        """Ferme proprement chaque Button (libère les broches GPIO)."""
        for button in self._buttons:
            button.close()  # type: ignore[attr-defined]
        self._buttons.clear()


class PiCamera(Camera):
    """Caméra réelle : à implémenter selon le module retenu (Pi Camera / webcam USB)."""

    def capture(self, destination_dir: Path) -> str:
        """Point d'extension : capturer une image réelle et renvoyer son chemin web."""
        raise NotImplementedError(
            "Capture réelle non implémentée : brancher la caméra puis compléter "
            "PiCamera.capture (picamera2 ou fswebcam)."
        )


class BenchScale(Scale):
    """Banc de pesée réel : à interfacer avec la balance existante du site."""

    def read_weight_kg(self) -> float:
        """Point d'extension : lire le poids depuis le banc (série / HX711 / API)."""
        raise NotImplementedError(
            "Lecture réelle du poids non implémentée : interfacer le banc de pesée."
        )
