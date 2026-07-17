from dataclasses import replace

import pytest

from app.calculations.normalization import percentile_rank, shrink_toward_midpoint
from app.calculations.style_scores import STYLE_FORMULAS, StyleFeatures, calculate_style_profile


def features(index: int, fights_count: int = 10) -> StyleFeatures:
    scale = float(index)
    return StyleFeatures(
        fights_count=fights_count,
        strike_attempts_per_minute=8 + scale,
        strike_differential_per_minute=-1 + scale / 4,
        opponent_output_suppression=scale / 10,
        knockdowns_per_15=scale / 5,
        significant_strikes_landed_per_minute=3 + scale / 2,
        striking_defence=0.45 + scale / 25,
        takedown_attempts_per_15=scale,
        takedowns_landed_per_15=scale / 2,
        control_seconds_per_15=scale * 20,
        submission_attempts_per_15=scale / 3,
        takedown_defence=0.4 + scale / 20,
        reversals_per_15=scale / 4,
        late_round_output_ratio=0.7 + scale / 20,
        knockdowns_absorbed_per_15=max(0, 2 - scale / 5),
        finish_loss_rate=max(0, 0.5 - scale / 20),
        output_consistency=0.4 + scale / 20,
    )


def test_percentile_rank_is_tie_aware_and_bounded() -> None:
    assert percentile_rank(2, [1, 2, 2, 3]) == 50
    assert percentile_rank(0, [1, 2, 3]) == 0
    assert percentile_rank(4, [1, 2, 3]) == 100
    assert percentile_rank(4, []) == 50


def test_full_sample_profile_uses_weight_class_percentiles() -> None:
    cohort = [features(index) for index in range(10)]
    profile = calculate_style_profile(cohort[-1], cohort, data_confidence=1.0)

    assert profile.scores["pressure_striking"].score == 95
    assert profile.scores["wrestling_pressure"].score == 95
    assert len(profile.scores) == len(STYLE_FORMULAS) == 13


def test_small_samples_shrink_scores_strongly_toward_50() -> None:
    cohort = [features(0), features(9)]
    fighter = replace(features(9), fights_count=1)

    profile = calculate_style_profile(fighter, cohort, data_confidence=0.8)

    assert profile.scores["pressure_striking"].confidence == pytest.approx(0.032)
    assert profile.scores["pressure_striking"].score == pytest.approx(50.8)


def test_each_style_score_is_explainable() -> None:
    cohort = [features(index) for index in range(10)]
    profile = calculate_style_profile(cohort[5], cohort, data_confidence=0.9)

    for score in profile.scores.values():
        assert 0 <= score.score <= 100
        assert score.contributing_features
        assert score.explanation


def test_archetypes_return_only_top_three_probabilities() -> None:
    cohort = [features(index) for index in range(10)]
    archetypes = calculate_style_profile(cohort[-1], cohort, data_confidence=1).archetypes

    assert len(archetypes) == 3
    assert all(0 <= probability <= 1 for probability in archetypes.values())
    assert list(archetypes.values()) == sorted(archetypes.values(), reverse=True)


def test_shrinkage_reliability_is_clamped() -> None:
    assert shrink_toward_midpoint(100, -1) == 50
    assert shrink_toward_midpoint(100, 2) == 100
