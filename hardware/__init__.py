"""Fabrique de la couche matérielle selon le mode configuré (sim / real)."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from config import HARDWARE_MODE
from hardware.base import ButtonPanel, Camera, RfidReader, Scale

logger = logging.getLogger(__name__)


@dataclass
class HardwareBundle:
    """Regroupe les quatre périphériques du poste."""

    reader: RfidReader
    scale: Scale
    camera: Camera
    buttons: ButtonPanel


def build_hardware(mode: str = HARDWARE_MODE) -> HardwareBundle:
    """Construit le jeu de périphériques correspondant au mode demandé.

    "sim"  : implémentations simulées (PC, sans câbles).
    "real" : implémentations Raspberry Pi (RC522, GPIO, caméra, banc de pesée).
    """
    if mode == "real":
        # Import localisé : les libs Pi ne sont chargées qu'en mode réel.
        from hardware.real import BenchScale, GpioButtonPanel, PiCamera, Rc522Reader

        logger.info("Initialisation du matériel réel")
        return HardwareBundle(
            reader=Rc522Reader(),
            scale=BenchScale(),
            camera=PiCamera(),
            buttons=GpioButtonPanel(),
        )

    if mode == "sim":
        from hardware.simulator import (
            SimulatedButtonPanel,
            SimulatedCamera,
            SimulatedRfidReader,
            SimulatedScale,
        )

        logger.info("Initialisation du matériel simulé")
        return HardwareBundle(
            reader=SimulatedRfidReader(),
            scale=SimulatedScale(),
            camera=SimulatedCamera(),
            buttons=SimulatedButtonPanel(),
        )

    raise ValueError(f"Mode matériel inconnu : {mode!r} (attendu 'sim' ou 'real').")
