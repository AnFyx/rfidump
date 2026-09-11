"""Serveur Flask du poste RFID : page web, flux SSE, commandes de simulation.

Le serveur ne fait que présenter l'état (poussé par le thread d'acquisition via
SSE) et exposer des commandes de simulation utiles tant que le matériel n'est
pas câblé. Les commandes de simulation sont refusées hors mode "sim".
"""

from __future__ import annotations

import json
import logging
from queue import Empty
from typing import Iterator

from flask import Flask, Response, abort, jsonify, render_template, request

import db
from config import (
    HARDWARE_MODE,
    HOST,
    MAX_SCORE,
    MAX_UID_LENGTH,
    MIN_SCORE,
    PHOTO_DIR,
    PORT,
    SSE_HEARTBEAT_INTERVAL,
)
from hardware import build_hardware
from station import Station

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# --- Initialisation -----------------------------------------------------
PHOTO_DIR.mkdir(parents=True, exist_ok=True)
db.init_db()
_hardware = build_hardware()
_station = Station(_hardware)
_station.start()

app = Flask(__name__)


@app.after_request
def set_security_headers(response: Response) -> Response:
    """Ajoute des en-têtes de sécurité de base à chaque réponse."""
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    # Tout en same-origin : pas de ressource ni de script tiers.
    response.headers["Content-Security-Policy"] = "default-src 'self'"
    return response


def _format_sse(payload: dict) -> str:
    """Met en forme un dictionnaire en message SSE (JSON)."""
    return f"data: {json.dumps(payload)}\n\n"


@app.route("/")
def index() -> str:
    """Sert la page principale du poste."""
    return render_template("index.html", sim_mode=(HARDWARE_MODE == "sim"))


@app.route("/state")
def state() -> Response:
    """Retourne l'état courant (pratique au chargement initial)."""
    return jsonify(_station.snapshot())


@app.route("/events")
def events() -> Response:
    """Flux SSE : pousse chaque changement d'état au navigateur."""
    subscriber = _station.broker.subscribe()
    if subscriber is None:
        response = Response("Trop de clients connectés\n", status=503, mimetype="text/plain")
        response.headers["Retry-After"] = str(int(SSE_HEARTBEAT_INTERVAL))
        return response

    def stream() -> Iterator[str]:
        try:
            # État courant immédiat, sans attendre le premier événement.
            yield _format_sse(_station.snapshot())
            while True:
                try:
                    payload = subscriber.get(timeout=SSE_HEARTBEAT_INTERVAL)
                    yield _format_sse(payload)
                except Empty:
                    # Pas d'événement : commentaire de maintien de connexion.
                    yield ": keepalive\n\n"
        finally:
            _station.broker.unsubscribe(subscriber)

    return Response(stream(), mimetype="text/event-stream")


# --- Endpoints de simulation (mode "sim" uniquement) -------------------
# Ils alimentent exactement les mêmes handlers que le matériel réel.


def _require_sim_json() -> dict:
    """Refuse hors mode sim, exige un corps JSON, et retourne le dictionnaire reçu.

    Exiger `Content-Type: application/json` empêche un site tiers de déclencher
    ces commandes par un simple formulaire : une requête JSON cross-origin impose
    une vérification préalable (preflight) que ce serveur n'autorise pas.
    """
    if HARDWARE_MODE != "sim":
        abort(403)
    if not request.is_json:
        abort(415, description="Corps JSON attendu")
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        abort(400, description="Objet JSON attendu")
    return payload


@app.route("/sim/present", methods=["POST"])
def sim_present() -> Response:
    """Simule la présentation d'un bac (UID dans le corps JSON)."""
    payload = _require_sim_json()
    uid = payload.get("uid")
    if not isinstance(uid, str) or not uid.strip() or len(uid) > MAX_UID_LENGTH:
        abort(400, description="UID manquant ou invalide")
    # En simulation, on tire un nouveau poids puis on injecte l'UID.
    _hardware.scale.new_load()  # type: ignore[attr-defined]
    _hardware.reader.present_tag(uid.strip())  # type: ignore[attr-defined]
    return jsonify({"ok": True})


@app.route("/sim/score", methods=["POST"])
def sim_score() -> Response:
    """Simule un appui sur un bouton étoile."""
    payload = _require_sim_json()
    value = payload.get("value")
    # bool est sous-type de int en Python : on l'exclut explicitement.
    if isinstance(value, bool) or not isinstance(value, int):
        abort(400, description="Note invalide")
    if not MIN_SCORE <= value <= MAX_SCORE:
        abort(400, description="Note hors bornes")
    _hardware.buttons.press_score(value)  # type: ignore[attr-defined]
    return jsonify({"ok": True})


@app.route("/sim/photo", methods=["POST"])
def sim_photo() -> Response:
    """Simule un appui sur le bouton photo."""
    _require_sim_json()
    _hardware.buttons.press_photo()  # type: ignore[attr-defined]
    return jsonify({"ok": True})


if __name__ == "__main__":
    try:
        # threaded=True : indispensable au SSE (un thread reste bloqué par client).
        # debug=False : jamais le débogueur Werkzeug en exploitation (RCE possible).
        app.run(host=HOST, port=PORT, threaded=True, debug=False)
    finally:
        _station.stop()
