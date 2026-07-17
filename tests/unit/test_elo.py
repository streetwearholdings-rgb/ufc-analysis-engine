from datetime import date, timedelta
from typing import Any
from uuid import UUID

import pytest

from app.calculations.elo import (
    EloConfig,
    EloFight,
    EloResult,
    RatingTrack,
    calculate_elo_history,
    expected_score,
    update_rating,
)

DAY = date(2026, 1, 1)
A = UUID(int=1)
B = UUID(int=2)
C = UUID(int=3)


def fight(index: int, result: EloResult, **changes: Any) -> EloFight:
    values: dict[str, Any] = {
        "fight_id": UUID(int=100 + index),
        "event_date": DAY + timedelta(days=index),
        "fighter_a_id": A,
        "fighter_b_id": B,
        "result": result,
    }
    values.update(changes)
    return EloFight(**values)


def test_expected_score_and_standard_update() -> None:
    assert expected_score(1500, 1500) == 0.5
    assert update_rating(1500, 1500, 1, k_factor=32) == 1516
    assert update_rating(1500, 1500, 0, k_factor=32) == 1484


def test_draw_between_equal_fighters_does_not_change_ratings() -> None:
    snapshot = calculate_elo_history([fight(0, EloResult.DRAW)])[0]

    assert snapshot.post_fight_a[RatingTrack.OVERALL] == 1500
    assert snapshot.post_fight_b[RatingTrack.OVERALL] == 1500


@pytest.mark.parametrize("result", [EloResult.NO_CONTEST, EloResult.OVERTURNED])
def test_invalidated_results_do_not_change_any_track(result: EloResult) -> None:
    snapshot = calculate_elo_history([fight(0, result)])[0]

    assert snapshot.pre_fight_a == snapshot.post_fight_a
    assert snapshot.pre_fight_b == snapshot.post_fight_b


def test_five_round_track_only_updates_for_five_round_fights() -> None:
    three_round = calculate_elo_history([fight(0, EloResult.FIGHTER_A_WIN)])[0]
    five_round = calculate_elo_history([fight(0, EloResult.FIGHTER_A_WIN, scheduled_rounds=5)])[0]

    assert three_round.post_fight_a[RatingTrack.FIVE_ROUND] == 1500
    assert five_round.post_fight_a[RatingTrack.FIVE_ROUND] == 1516


def test_discipline_results_can_differ_from_overall_result() -> None:
    snapshot = calculate_elo_history(
        [
            fight(
                0,
                EloResult.FIGHTER_A_WIN,
                track_results={RatingTrack.STRIKING: 0.0, RatingTrack.WRESTLING: 1.0},
            )
        ]
    )[0]

    assert snapshot.post_fight_a[RatingTrack.OVERALL] > 1500
    assert snapshot.post_fight_a[RatingTrack.STRIKING] < 1500
    assert snapshot.post_fight_a[RatingTrack.WRESTLING] > 1500


def test_configured_multipliers_scale_rating_change() -> None:
    standard = calculate_elo_history([fight(0, EloResult.FIGHTER_A_WIN)])[0]
    amplified = calculate_elo_history(
        [fight(0, EloResult.FIGHTER_A_WIN)], EloConfig(method_multiplier=1.5, dominance_multiplier=1.2)
    )[0]

    assert amplified.post_fight_a[RatingTrack.OVERALL] - 1500 > standard.post_fight_a[RatingTrack.OVERALL] - 1500


def test_future_fight_does_not_change_earlier_historical_snapshot() -> None:
    first = fight(0, EloResult.FIGHTER_A_WIN)
    original = calculate_elo_history([first])[0]
    with_future = calculate_elo_history([fight(10, EloResult.FIGHTER_B_WIN, fighter_b_id=C), first])[0]

    assert with_future == original


def test_pre_fight_rating_uses_only_prior_results() -> None:
    history = calculate_elo_history([fight(1, EloResult.FIGHTER_B_WIN), fight(0, EloResult.FIGHTER_A_WIN)])

    assert history[1].pre_fight_a == history[0].post_fight_a
    assert history[1].pre_fight_b == history[0].post_fight_b
