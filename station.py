"""Logique métier du poste : état courant, diffusion d'événements, traitements.

Séparation nette des responsabilités :
- la boucle de scrutation (thread de fond) parle au matériel et met à jour l'état ;
- l'EventBroker pousse chaque changement d'état aux clients web abonnés (SSE) ;
- Flask ne fait que lire l'état et s'abonner au broker (cf. app.py).
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import asdict, dataclass
from queue import Full, Queue
from typing import Callable, List, Optional

from config import (
    MAX_SCORE,
    MIN_SCORE,
    PHOTO_DIR,
    RESCAN_GRACE_PERIOD_S,
    RFID_POLL_INTERVAL_S,
    SSE_MAX_CLIENTS,
    SSE_QUEUE_MAXSIZE,
)
from db import attach_photo, lookup_bin, record_weighing
from hardware import HardwareBundle

logger = logging.getLogger(__name__)


@dataclass
class StationSnapshot:
    """Photographie de l'état courant du poste, envoyée au client web."""

    uid: Optional[str] = None
    etablissement: Optional[str] = None
    weight_kg: Optional[float] = None
    score: Optional[int] = None
    photo_path: Optional[str] = None
    bin_known: bool = False
    message: str = "En attente d'un bac"


class EventBroker:
    """Diffuse les événements d'état à tous les clients SSE abonnés."""

    def __init__(self, max_subscribers: int = SSE_MAX_CLIENTS) -> None:
        self._subscribers: List[Queue] = []
        self._lock = threading.Lock()
        self._max_subscribers = max_subscribers

    def subscribe(self) -> Optional[Queue]:
        """Crée une file bornée pour un nouveau client, ou None si la limite est atteinte."""
        with self._lock:
            if len(self._subscribers) >= self._max_subscribers:
                logger.warning("Limite de clients SSE atteinte : connexion refusée")
                return None
            subscriber: Queue = Queue(maxsize=SSE_QUEUE_MAXSIZE)
            self._subscribers.append(subscriber)
        return subscriber

    def unsubscribe(self, subscriber: Queue) -> None:
        """Retire un client (déconnexion)."""
        with self._lock:
            if subscriber in self._subscribers:
                self._subscribers.remove(subscriber)

    def publish(self, payload: dict) -> None:
        """Pousse un événement à tous les clients ; saute les files saturées."""
        with self._lock:
            subscribers = list(self._subscribers)
        for subscriber in subscribers:
            try:
                subscriber.put_nowait(payload)
            except Full:
                # Client trop lent : on saute l'événement plutôt que de bloquer le poste.
                logger.warning("File SSE saturée : événement ignoré pour un client")


class Station:
    """Coordonne le matériel, l'état courant et la diffusion vers le web."""

    def __init__(
        self,
        hardware: HardwareBundle,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._hardware = hardware
        self._broker = EventBroker()
        self._state = StationSnapshot()
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._poll_thread: Optional[threading.Thread] = None
        # Horloge injectable (tests) pour la fenêtre de relecture d'un même tag.
        self._clock = clock
        self._last_scan_uid: Optional[str] = None
        self._last_scan_at = 0.0
        # Identifiant de la pesée enregistrée pour le bac courant (None avant la note).
        self._weighing_id: Optional[int] = None

    @property
    def broker(self) -> EventBroker:
        """Expose le broker pour l'endpoint SSE."""
        return self._broker

    def snapshot(self) -> dict:
        """Retourne une copie sérialisable de l'état courant."""
        with self._lock:
            return asdict(self._state)

    # --- Cycle de vie ---------------------------------------------------

    def start(self) -> None:
        """Câble les boutons et démarre la boucle de scrutation RFID."""
        self._hardware.buttons.start(
            on_score=self.handle_score,
            on_photo=self.handle_photo,
        )
        self._poll_thread = threading.Thread(
            target=self._poll_loop, name="rfid-poll", daemon=True
        )
        self._poll_thread.start()
        logger.info("Poste démarré")

    def stop(self) -> None:
        """Arrête proprement la scrutation et libère les boutons."""
        self._stop_event.set()
        self._hardware.buttons.stop()
        if self._poll_thread is not None:
            self._poll_thread.join(timeout=2.0)

    # --- Boucle d'acquisition ------------------------------------------

    def _poll_loop(self) -> None:
        """Scrute le lecteur RFID en continu et traite chaque tag détecté."""
        while not self._stop_event.is_set():
            try:
                uid = self._hardware.reader.read_uid()
                if uid is not None:
                    self.handle_scan(uid)
            except Exception:
                # On logge et on poursuit : une lecture ratée ne doit pas tuer le poste.
                logger.exception("Erreur pendant la scrutation RFID")
            self._stop_event.wait(RFID_POLL_INTERVAL_S)

    # --- Traitements métier --------------------------------------------

    def handle_scan(self, uid: str) -> None:
        """Traite la présentation d'un bac : résolution établissement + pesée.

        Un tag laissé sur le banc est relu à chaque scrutation : sans garde, chaque
        relecture relancerait un cycle (note effacée, nouvelle pesée possible, photo
        perdue). Une relecture du même UID dans RESCAN_GRACE_PERIOD_S est donc
        ignorée, et prolonge la présentation en cours.
        """
        now = self._clock()
        with self._lock:
            same_presentation = (
                uid == self._last_scan_uid
                and now - self._last_scan_at < RESCAN_GRACE_PERIOD_S
            )
            self._last_scan_uid = uid
            self._last_scan_at = now
        if same_presentation:
            return

        etablissement = lookup_bin(uid)
        weight = self._hardware.scale.read_weight_kg()
        known = etablissement is not None
        with self._lock:
            self._state = StationSnapshot(
                uid=uid,
                etablissement=etablissement,
                weight_kg=weight,
                score=None,
                photo_path=None,
                bin_known=known,
                message=(
                    "Bac reconnu — en attente de la note"
                    if known
                    else "Bac INCONNU — vérifier le tag"
                ),
            )
            self._weighing_id = None
        self._publish_state()

    def handle_score(self, value: int) -> None:
        """Enregistre la note (1-3 étoiles) du bac courant et clôt le cycle.

        `value` peut provenir d'un bouton physique ou de l'UI de simulation :
        on revalide systématiquement les bornes côté serveur.
        """
        if not MIN_SCORE <= value <= MAX_SCORE:
            logger.warning("Note hors bornes ignorée : %r", value)
            return
        with self._lock:
            state = self._state
            if state.uid is None:
                logger.info("Note reçue sans bac présent : ignorée")
                return
            if not state.bin_known or state.etablissement is None:
                logger.info("Note refusée : bac inconnu")
                return
            if state.score is not None:
                # Double appui (gants, rebond) : une seule pesée par présentation.
                logger.info("Note déjà enregistrée pour ce bac : appui ignoré")
                return
            weight = state.weight_kg if state.weight_kg is not None else 0.0
            self._weighing_id = record_weighing(
                uid=state.uid,
                etablissement=state.etablissement,
                weight_kg=weight,
                score=value,
                photo_path=state.photo_path,
            )
            self._state.score = value
            self._state.message = "Pesée enregistrée"
        self._publish_state()

    def handle_photo(self) -> None:
        """Capture une photo de justification et l'attache au bac courant.

        Prise avant la note, la photo est enregistrée avec la pesée. Prise après,
        elle est rattachée à la pesée déjà créée au lieu d'être perdue.
        """
        with self._lock:
            requested_for_uid = self._state.uid
        if requested_for_uid is None:
            logger.info("Photo demandée sans bac présent : ignorée")
            return
        # La capture peut être lente : on la fait hors verrou.
        photo_path = self._hardware.camera.capture(PHOTO_DIR)
        with self._lock:
            if self._state.uid != requested_for_uid:
                logger.warning("Bac changé pendant la capture : photo non rattachée")
                return
            self._state.photo_path = photo_path
            if self._weighing_id is not None:
                attach_photo(self._weighing_id, photo_path)
                self._state.message = "Photo ajoutée à la pesée"
            else:
                self._state.message = "Photo capturée"
        self._publish_state()

    def _publish_state(self) -> None:
        """Diffuse l'état courant à tous les clients web."""
        self._broker.publish(self.snapshot())
