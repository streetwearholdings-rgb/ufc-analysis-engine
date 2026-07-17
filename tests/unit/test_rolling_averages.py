from dataclasses import replace
from datetime import date, timedelta
from typing import Any
from uuid import UUID

import pytest

from app.calculations.rolling_averages import (
    FightStatLine,
    RollingWindow,
    build_fight_stat_line,
    calculate_rolling_metrics,
)
from app.database.models.fight import Fight, FightResult
from app.database.models.fight_round_stat import FightRoundStat

BASE_DATE = date(2026, 7, 1)


def stat_line(index: int, **changes: Any) -> FightStatLine:
    baseline = FightStatLine(
        fight_id=UUID(int=index + 1),
        event_date=BASE_DATE - timedelta(days=index),
        result=FightResult.FIGHTER_A_WIN,
        won=True,
        method="Unanimous Decision",
        elapsed_seconds=300,
        rounds_observed=1,
        significant_strikes_landed=30,
        significant_strikes_attempted=60,
        significant_strikes_absorbed=20,
        opponent_significant_strikes_attempted=50,
        knockdowns=1,
        knockdowns_absorbed=0,
        takedowns_landed=2,
        takedowns_attempted=4,
        opponent_takedowns_landed=1,
        opponent_takedowns_attempted=4,
        control_time_seconds=60,
        opponent_control_time_seconds=30,
        submission_attempts=1,
        early_output=20,
        early_seconds=200,
        late_output=10,
        late_seconds=100,
    )
    return replace(baseline, **changes)


def test_per_minute_and_per_15_use_elapsed_time() -> None:
    metrics = calculate_rolling_metrics([stat_line(0)], RollingWindow.LAST_3)

    assert metrics.minutes_observed == 5
    assert metrics.significant_strikes_landed_per_minute == 6
    assert metrics.significant_strikes_absorbed_per_minute == 4
    assert metrics.significant_strike_differential_per_minute == 2
    assert metrics.knockdowns_per_15 == 3
    assert metrics.takedowns_landed_per_15 == 6
    assert metrics.control_seconds_per_15 == 180


def test_accuracy_and_defence_are_attempt_based() -> None:
    metrics = calculate_rolling_metrics([stat_line(0)], RollingWindow.LAST_3)

    assert metrics.significant_strike_accuracy == 0.5
    assert metrics.significant_strike_defence == 0.6
    assert metrics.takedown_accuracy == 0.5
    assert metrics.takedown_defence == 0.75


@pytest.mark.parametrize(
    ("window", "expected_count", "expected_landed"),
    [(RollingWindow.LAST_3, 3, 4.0), (RollingWindow.LAST_5, 5, 6.0)],
)
def test_rolling_windows_select_most_recent_fights(
    window: RollingWindow, expected_count: int, expected_landed: float
) -> None:
    fights = [stat_line(index, significant_strikes_landed=(index + 1) * 10) for index in range(6)]

    metrics = calculate_rolling_metrics(fights, window)

    assert metrics.fights_count == expected_count
    assert metrics.significant_strikes_landed_per_minute == expected_landed


def test_no_contest_and_overturned_are_excluded_from_win_rate() -> None:
    fights = [
        stat_line(0, won=True),
        stat_line(1, won=False, result=FightResult.FIGHTER_B_WIN),
        stat_line(2, won=True, result=FightResult.NO_CONTEST),
        stat_line(3, won=True, result=FightResult.OVERTURNED),
    ]

    metrics = calculate_rolling_metrics(fights, RollingWindow.LAST_5)

    assert metrics.win_rate == 0.5


def test_empty_window_has_zero_metrics_without_division_error() -> None:
    metrics = calculate_rolling_metrics([], RollingWindow.LAST_3)

    assert metrics.fights_count == 0
    assert metrics.minutes_observed == 0
    assert metrics.significant_strike_accuracy == 0
    assert metrics.takedown_defence == 0
    assert metrics.win_rate == 0


def test_finish_rates_use_wins_as_denominator() -> None:
    fights = [
        stat_line(0, method="KO/TKO"),
        stat_line(1, method="Submission"),
        stat_line(2, method="Split Decision"),
        stat_line(3, won=False, result=FightResult.FIGHTER_B_WIN, method="KO/TKO"),
    ]

    metrics = calculate_rolling_metrics(fights, RollingWindow.LAST_5)

    assert metrics.finish_rate == pytest.approx(2 / 3)
    assert metrics.knockout_rate == pytest.approx(1 / 3)
    assert metrics.submission_rate == pytest.approx(1 / 3)
    assert metrics.decision_rate == pytest.approx(1 / 3)


def test_fight_aggregation_uses_only_fighters_observed_round_time() -> None:
    fighter_id = UUID(int=100)
    opponent_id = UUID(int=200)
    fight = Fight(
        id=UUID(int=300),
        result=FightResult.FIGHTER_A_WIN,
        winner_id=fighter_id,
        method="KO/TKO",
    )
    rows = [
        FightRoundStat(
            fighter_id=fighter_id,
            opponent_id=opponent_id,
            round_number=1,
            round_duration_seconds=300,
            significant_strikes_landed=20,
            significant_strikes_attempted=40,
            takedowns_landed=1,
            takedowns_attempted=2,
            knockdowns=0,
            control_time_seconds=20,
            submission_attempts=0,
        ),
        FightRoundStat(
            fighter_id=fighter_id,
            opponent_id=opponent_id,
            round_number=2,
            round_duration_seconds=75,
            significant_strikes_landed=10,
            significant_strikes_attempted=15,
            takedowns_landed=0,
            takedowns_attempted=0,
            knockdowns=1,
            control_time_seconds=5,
            submission_attempts=0,
        ),
        FightRoundStat(
            fighter_id=opponent_id,
            opponent_id=fighter_id,
            round_number=1,
            round_duration_seconds=300,
            significant_strikes_landed=12,
            significant_strikes_attempted=30,
            takedowns_landed=0,
            takedowns_attempted=1,
            knockdowns=0,
            control_time_seconds=10,
            submission_attempts=0,
        ),
        FightRoundStat(
            fighter_id=opponent_id,
            opponent_id=fighter_id,
            round_number=2,
            round_duration_seconds=75,
            significant_strikes_landed=4,
            significant_strikes_attempted=9,
            takedowns_landed=0,
            takedowns_attempted=0,
            knockdowns=0,
            control_time_seconds=0,
            submission_attempts=0,
        ),
    ]

    line = build_fight_stat_line(fighter_id, fight, BASE_DATE, rows)

    assert line.elapsed_seconds == 375
    assert line.rounds_observed == 2
    assert line.significant_strikes_landed == 30
    assert line.significant_strikes_absorbed == 16
