from datetime import date, timedelta

import pytest

from app.calculations.recency import decay_lambda, recency_weight


def test_recent_fight_has_more_weight_than_old_fight() -> None:
    today = date(2026, 7, 16)
    assert recency_weight(today - timedelta(days=30), today) > recency_weight(today - timedelta(days=900), today)


def test_half_life_fight_receives_half_weight() -> None:
    today = date(2026, 7, 16)
    assert recency_weight(today - timedelta(days=730), today, 730) == pytest.approx(0.5)


def test_weights_are_never_negative() -> None:
    today = date(2026, 7, 16)
    assert all(recency_weight(today - timedelta(days=days), today) >= 0 for days in (0, 1, 730, 10_000))


def test_invalid_half_life_and_future_fights_are_rejected() -> None:
    today = date(2026, 7, 16)
    with pytest.raises(ValueError, match="half-life"):
        decay_lambda(0)
    with pytest.raises(ValueError, match="after"):
        recency_weight(today + timedelta(days=1), today)
