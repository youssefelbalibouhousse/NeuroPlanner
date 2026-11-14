"""Minuteur pur : précision, pause, reprise, fin — sans interface ni attente réelle."""

from __future__ import annotations

import pytest

from neuroplanner.services.countdown import Countdown


class FakeClock:
    """Horloge contrôlée : rend les tests instantanés et déterministes."""

    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


def test_initial_state(clock: FakeClock) -> None:
    timer = Countdown(60, clock=clock)
    assert timer.remaining == 60
    assert timer.display_seconds == 60
    assert timer.progress == 1.0
    assert timer.running is False
    assert timer.finished is False


@pytest.mark.parametrize("duration", [0, -1, -0.5])
def test_rejects_non_positive_duration(duration: float, clock: FakeClock) -> None:
    with pytest.raises(ValueError):
        Countdown(duration, clock=clock)


def test_counts_down_while_running(clock: FakeClock) -> None:
    timer = Countdown(60, clock=clock)
    timer.start()
    clock.advance(15)
    assert timer.remaining == pytest.approx(45)
    assert timer.display_seconds == 45
    assert timer.progress == pytest.approx(0.75)


def test_display_seconds_never_shows_zero_early(clock: FakeClock) -> None:
    timer = Countdown(60, clock=clock)
    timer.start()
    clock.advance(59.2)
    assert timer.display_seconds == 1


def test_tick_reports_completion_once(clock: FakeClock) -> None:
    timer = Countdown(30, clock=clock)
    timer.start()

    clock.advance(10)
    assert timer.tick() is False

    clock.advance(25)
    assert timer.tick() is True
    assert timer.finished is True
    assert timer.running is False

    clock.advance(5)
    assert timer.tick() is False


def test_pause_freezes_then_resumes(clock: FakeClock) -> None:
    timer = Countdown(100, clock=clock)
    timer.start()
    clock.advance(40)

    timer.pause()
    assert timer.running is False
    assert timer.remaining == pytest.approx(60)

    clock.advance(1000)  # le temps qui passe ne consomme plus rien
    assert timer.remaining == pytest.approx(60)

    timer.start()
    clock.advance(20)
    assert timer.remaining == pytest.approx(40)


def test_pause_is_idempotent(clock: FakeClock) -> None:
    timer = Countdown(100, clock=clock)
    timer.pause()
    assert timer.remaining == pytest.approx(100)


def test_cannot_start_twice(clock: FakeClock) -> None:
    timer = Countdown(100, clock=clock)
    timer.start()
    clock.advance(10)
    first_remaining = timer.remaining
    timer.start()  # ignoré
    assert timer.remaining == pytest.approx(first_remaining)


def test_reset_restores_full_duration(clock: FakeClock) -> None:
    timer = Countdown(100, clock=clock)
    timer.start()
    clock.advance(99)
    timer.reset()
    assert timer.remaining == 100
    assert timer.running is False
    assert timer.finished is False


def test_start_after_finish_restarts(clock: FakeClock) -> None:
    timer = Countdown(10, clock=clock)
    timer.start()
    clock.advance(11)
    assert timer.tick() is True

    timer.start()
    assert timer.finished is False
    assert timer.remaining == pytest.approx(10)


def test_set_duration_resets(clock: FakeClock) -> None:
    timer = Countdown(100, clock=clock)
    timer.start()
    clock.advance(50)

    timer.set_duration(180)
    assert timer.duration == 180
    assert timer.remaining == 180
    assert timer.running is False


def test_set_duration_validates(clock: FakeClock) -> None:
    timer = Countdown(10, clock=clock)
    with pytest.raises(ValueError):
        timer.set_duration(0)


def test_progress_is_clamped(clock: FakeClock) -> None:
    timer = Countdown(10, clock=clock)
    timer.start()
    clock.advance(100)  # bien au-delà de la durée
    assert timer.remaining == 0.0
    assert timer.progress == 0.0
