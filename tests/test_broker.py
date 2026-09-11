"""Tests du diffuseur d'événements SSE."""

from __future__ import annotations

from station import EventBroker


def test_subscribers_beyond_limit_are_refused() -> None:
    broker = EventBroker(max_subscribers=2)
    first = broker.subscribe()
    second = broker.subscribe()
    assert first is not None and second is not None
    assert broker.subscribe() is None

    broker.unsubscribe(first)
    assert broker.subscribe() is not None


def test_publish_skips_a_full_queue_without_blocking() -> None:
    broker = EventBroker(max_subscribers=1)
    subscriber = broker.subscribe()
    assert subscriber is not None
    for index in range(subscriber.maxsize + 5):
        broker.publish({"index": index})  # ne doit jamais bloquer
    assert subscriber.full()
