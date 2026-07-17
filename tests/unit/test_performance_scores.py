import pytest

from app.calculations.performance_scores import (
    PerformanceInput,
    PerformanceResult,
    PerformanceWeights,
    calculate_performance_score,
)


def test_default_weighted_score_matches_documented_formula() -> None:
    result = calculate_performance_score(
        PerformanceInput(
            result=PerformanceResult.WIN,
            knockdowns=1,
            significant_head_strikes=25,
            significant_strike_differential_per_minute=2,
            significant_strike_accuracy=0.55,
            defensive_avoidance=0.65,
            significant_strike_output_per_minute=6,
            takedowns_landed=2,
            takedown_accuracy=0.5,
            submission_attempts=1,
            control_duration_seconds=120,
            significant_ground_strikes=12,
            method="KO/TKO",
            finish_round=2,
        )
    )

    expected = (
        result.damage.score * 0.30
        + result.striking.score * 0.20
        + result.grappling.score * 0.20
        + result.control.score * 0.15
        + result.result_quality.score * 0.15
    )
    assert result.raw_performance_score == pytest.approx(expected)
    assert result.final_performance_score == result.raw_performance_score


def test_every_component_is_bounded_and_explained() -> None:
    result = calculate_performance_score(
        PerformanceInput(
            result=PerformanceResult.WIN,
            knockdowns=20,
            significant_head_strikes=500,
            significant_strike_differential_per_minute=50,
            significant_strike_accuracy=3,
            defensive_avoidance=3,
            significant_strike_output_per_minute=100,
            takedowns_landed=20,
            takedown_accuracy=3,
            submission_attempts=20,
            reversals=20,
            control_duration_seconds=2000,
            activity_factor=2,
            advancement_factor=2,
        )
    )

    for component in (
        result.damage,
        result.striking,
        result.grappling,
        result.control,
        result.result_quality,
    ):
        assert 0 <= component.score <= 100
        assert component.features
        assert component.explanation


def test_passive_control_scores_lower_than_active_control() -> None:
    passive = calculate_performance_score(PerformanceInput(result=PerformanceResult.WIN, control_duration_seconds=300))
    active = calculate_performance_score(
        PerformanceInput(
            result=PerformanceResult.WIN,
            control_duration_seconds=300,
            significant_ground_strikes=20,
            submission_attempts=2,
            advancement_factor=0.9,
        )
    )

    assert active.control.score > passive.control.score


def test_competitive_elite_loss_can_outscore_weak_win() -> None:
    elite_loss = calculate_performance_score(
        PerformanceInput(
            result=PerformanceResult.LOSS,
            opponent_rating=1900,
            knockdowns=1,
            significant_head_strikes=35,
            significant_strike_differential_per_minute=2.5,
            significant_strike_accuracy=0.62,
            defensive_avoidance=0.7,
            significant_strike_output_per_minute=7,
            takedowns_landed=2,
            takedown_accuracy=0.66,
            submission_attempts=2,
            control_duration_seconds=150,
            significant_ground_strikes=15,
        )
    )
    weak_win = calculate_performance_score(
        PerformanceInput(result=PerformanceResult.WIN, opponent_rating=1200, method="Unanimous Decision")
    )

    assert elite_loss.final_performance_score > weak_win.final_performance_score


def test_invalid_weights_are_rejected() -> None:
    with pytest.raises(ValueError, match="sum to 1"):
        PerformanceWeights(damage=0.5)
