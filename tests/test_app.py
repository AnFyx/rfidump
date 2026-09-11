"""Tests des endpoints HTTP (mode simulation, base temporaire)."""

from __future__ import annotations

from typing import Iterator

import pytest

import app as station_app
import config
from config import MAX_UID_LENGTH, SSE_MAX_CLIENTS


@pytest.fixture
def client() -> Iterator:
    return station_app.app.test_client()


def test_index_sets_security_headers(client) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert response.headers["Content-Security-Policy"] == "default-src 'self'"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["X-Content-Type-Options"] == "nosniff"


@pytest.mark.parametrize("endpoint", ["/sim/present", "/sim/score", "/sim/photo"])
def test_simulation_commands_require_json(client, endpoint: str) -> None:
    response = client.post(endpoint, data="value=3", content_type="application/x-www-form-urlencoded")
    assert response.status_code == 415


@pytest.mark.parametrize(
    "body",
    [{}, {"uid": ""}, {"uid": 42}, {"uid": "X" * (MAX_UID_LENGTH + 1)}],
)
def test_invalid_uid_is_rejected(client, body: dict) -> None:
    assert client.post("/sim/present", json=body).status_code == 400


@pytest.mark.parametrize("value", [True, "3", 0, 4, None])
def test_invalid_score_is_rejected(client, value) -> None:
    assert client.post("/sim/score", json={"value": value}).status_code == 400


@pytest.mark.parametrize("endpoint", ["/sim/present", "/sim/score", "/sim/photo"])
def test_simulation_commands_are_refused_in_real_mode(
    client, monkeypatch: pytest.MonkeyPatch, endpoint: str
) -> None:
    monkeypatch.setattr(station_app, "HARDWARE_MODE", "real")
    assert client.post(endpoint, json={"uid": "DEMO-UID-0001", "value": 2}).status_code == 403


def test_event_stream_refuses_clients_beyond_limit(client) -> None:
    broker = station_app._station.broker
    held = []
    try:
        while (subscriber := broker.subscribe()) is not None:
            held.append(subscriber)
        assert len(held) <= SSE_MAX_CLIENTS
        response = client.get("/events")
        assert response.status_code == 503
        assert "Retry-After" in response.headers
    finally:
        for subscriber in held:
            broker.unsubscribe(subscriber)


def test_default_host_is_localhost() -> None:
    assert config.HOST == "127.0.0.1"


@pytest.mark.parametrize("raw", ["abc", "0", "70000"])
def test_invalid_port_fails_closed(raw: str) -> None:
    with pytest.raises(ValueError):
        config._read_port(raw)
