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

    def stream() -> Iterator[str]:
        subscriber = _station.broker.subscribe()
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


@app.route("/sim/present", methods=["POST"])
def sim_present() -> Response:
    """Simule la présentation d'un bac (UID dans le corps JSON)."""
    if HARDWARE_MODE != "sim":
        abort(403)
    payload = request.get_json(silent=True) or {}
    uid = payload.get("uid")
    if not isinstance(uid, str) or not uid.strip():
        abort(400, description="UID manquant ou invalide")
    # En simulation, on tire un nouveau poids puis on injecte l'UID.
    _hardware.scale.new_load()  # type: ignore[attr-defined]
    _hardware.reader.present_tag(uid.strip())  # type: ignore[attr-defined]
    return jsonify({"ok": True})


@app.route("/sim/score", methods=["POST"])
def sim_score() -> Response:
    """Simule un appui sur un bouton étoile."""
    if HARDWARE_MODE != "sim":
        abort(403)
    payload = request.get_json(silent=True) or {}
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
    if HARDWARE_MODE != "sim":
        abort(403)
    _hardware.buttons.press_photo()  # type: ignore[attr-defined]
    return jsonify({"ok": True})


if __name__ == "__main__":
    try:
        # threaded=True : indispensable au SSE (un thread reste bloqué par client).
        # debug=False : jamais le débogueur Werkzeug en exploitation (RCE possible).
        app.run(host=HOST, port=PORT, threaded=True, debug=False)
    finally:
        _station.stop()
