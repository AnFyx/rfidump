"""Tests de la logique métier du poste, avec un matériel factice et une horloge pilotée."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

import pytest

from config import RESCAN_GRACE_PERIOD_S
from hardware import HardwareBundle
from hardware.base import ButtonPanel, Camera, RfidReader, Scale
from station import Station
from tests.conftest import fetch_weighings

KNOWN_UID = "DEMO-UID-0001"
UNKNOWN_UID = "UID-INCONNU-9999"
TEST_WEIGHT_KG = 21.5
TEST_PHOTO = "photos/test.jpg"


class FakeReader(RfidReader):
    def read_uid(self) -> Optional[str]:
        return None


class FakeScale(Scale):
    def read_weight_kg(self) -> float:
        return TEST_WEIGHT_KG


class FakeCamera(Camera):
    def __init__(self) -> None:
        self.captures = 0

    def capture(self, destination_dir: Path) -> str:
        self.captures += 1
        return TEST_PHOTO


class FakeButtons(ButtonPanel):
    def start(self, on_score: Callable[[int], None], on_photo: Callable[[], None]) -> None:
        pass

    def stop(self) -> None:
        pass


class FakeClock:
    """Horloge monotone pilotée par le test."""

    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def camera() -> FakeCamera:
    return FakeCamera()


@pytest.fixture
def station(fresh_db: Path, clock: FakeClock, camera: FakeCamera) -> Station:
    hardware = HardwareBundle(
        reader=FakeReader(), scale=FakeScale(), camera=camera, buttons=FakeButtons()
    )
    return Station(hardware, clock=clock)


def test_known_bin_waits_for_score(station: Station) -> None:
    station.handle_scan(KNOWN_UID)
    state = station.snapshot()
    assert state["bin_known"] is True
    assert state["weight_kg"] == TEST_WEIGHT_KG
    assert state["score"] is None


def test_score_records_one_weighing(station: Station, fresh_db: Path) -> None:
    station.handle_scan(KNOWN_UID)
    station.handle_score(2)
    assert fetch_weighings(fresh_db) == [(KNOWN_UID, TEST_WEIGHT_KG, 2, None)]


def test_second_score_press_is_ignored(station: Station, fresh_db: Path) -> None:
    station.handle_scan(KNOWN_UID)
    station.handle_score(2)
    station.handle_score(3)
    assert len(fetch_weighings(fresh_db)) == 1
    assert station.snapshot()["score"] == 2


def test_tag_left_on_bench_does_not_restart_the_cycle(
    station: Station, clock: FakeClock, fresh_db: Path
) -> None:
    """Régression : un tag relu à chaque scrutation ne doit pas permettre une nouvelle pesée."""
    station.handle_scan(KNOWN_UID)
    station.handle_score(2)
    for _ in range(5):
        clock.now += 0.2  # scrutations successives, tag toujours présent
        station.handle_scan(KNOWN_UID)
        station.handle_score(3)
    assert len(fetch_weighings(fresh_db)) == 1
    assert station.snapshot()["score"] == 2


def test_bin_presented_again_after_grace_period_starts_new_cycle(
    station: Station, clock: FakeClock, fresh_db: Path
) -> None:
    station.handle_scan(KNOWN_UID)
    station.handle_score(2)
    clock.now += RESCAN_GRACE_PERIOD_S + 1.0  # bac retiré puis représenté
    station.handle_scan(KNOWN_UID)
    assert station.snapshot()["score"] is None
    station.handle_score(1)
    assert [row[2] for row in fetch_weighings(fresh_db)] == [2, 1]


def test_unknown_bin_cannot_be_scored(station: Station, fresh_db: Path) -> None:
    station.handle_scan(UNKNOWN_UID)
    station.handle_score(2)
    assert fetch_weighings(fresh_db) == []
    assert station.snapshot()["bin_known"] is False


@pytest.mark.parametrize("value", [0, 4, -1])
def test_out_of_bounds_score_is_ignored(station: Station, fresh_db: Path, value: int) -> None:
    station.handle_scan(KNOWN_UID)
    station.handle_score(value)
    assert fetch_weighings(fresh_db) == []


def test_photo_before_score_is_saved_with_the_weighing(
    station: Station, fresh_db: Path
) -> None:
    station.handle_scan(KNOWN_UID)
    station.handle_photo()
    station.handle_score(3)
    assert fetch_weighings(fresh_db) == [(KNOWN_UID, TEST_WEIGHT_KG, 3, TEST_PHOTO)]


def test_photo_after_score_is_attached_to_the_weighing(
    station: Station, fresh_db: Path
) -> None:
    """Régression : une photo prise après la note était perdue."""
    station.handle_scan(KNOWN_UID)
    station.handle_score(3)
    station.handle_photo()
    assert fetch_weighings(fresh_db) == [(KNOWN_UID, TEST_WEIGHT_KG, 3, TEST_PHOTO)]


def test_photo_without_bin_is_ignored(station: Station, camera: FakeCamera) -> None:
    station.handle_photo()
    assert camera.captures == 0
