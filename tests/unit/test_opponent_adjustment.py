from datetime import date

import pytest

from app.calculations.opponent_adjustment import (
    HistoricalOpponentMetric,
    adjust_offensive_output,
    calculate_defensive_suppression,
)

FIGHT_DATE = date(2026, 6, 1)


def test_offensive_adjustment_uses_opponent_and_division_baselines() -> None:
    result = adjust_offensive_output(
        6.0,
        HistoricalOpponentMetric(date(2026, 5, 1), average_allowed=4.0, fights_count=5),
        division_average_allowed=5.0,
        fight_date=FIGHT_DATE,
        minimum_fights=3,
    )

    assert result.adjusted_value == pytest.approx(7.5)
    assert result.meets_minimum_sample is True
    assert result.sample_confidence == 1.0


def test_small_samples_shrink_toward_division_average() -> None:
    result = adjust_offensive_output(
        6.0,
        HistoricalOpponentMetric(date(2026, 5, 1), average_allowed=2.0, fights_count=1),
        division_average_allowed=5.0,
        fight_date=FIGHT_DATE,
        minimum_fights=4,
    )

    assert result.shrunk_opponent_baseline == pytest.approx(4.25)
    assert result.sample_confidence == 0.25
    assert result.meets_minimum_sample is False


def test_zero_baseline_uses_safe_denominator() -> None:
    result = adjust_offensive_output(
        1.0,
        HistoricalOpponentMetric(date(2026, 5, 1), average_allowed=0.0, fights_count=10),
        division_average_allowed=0.0,
        fight_date=FIGHT_DATE,
    )

    assert result.adjusted_value == 0.0


def test_defensive_suppression_is_expected_minus_actual() -> None:
    result = calculate_defensive_suppression(
        3.5,
        HistoricalOpponentMetric(date(2026, 5, 1), average_allowed=5.5, fights_count=5),
        division_average_output=5.0,
        fight_date=FIGHT_DATE,
    )

    assert result.adjusted_value == 2.0


@pytest.mark.parametrize("snapshot_date", [FIGHT_DATE, date(2026, 7, 1)])
def test_same_day_or_future_opponent_data_is_rejected(snapshot_date: date) -> None:
    with pytest.raises(ValueError, match="before the fight"):
        adjust_offensive_output(
            5.0,
            HistoricalOpponentMetric(snapshot_date, average_allowed=5.0, fights_count=5),
            division_average_allowed=5.0,
            fight_date=FIGHT_DATE,
        )
