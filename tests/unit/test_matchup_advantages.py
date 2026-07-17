from dataclasses import replace
from typing import Any
from uuid import UUID

import pytest

from app.calculations.matchup_advantages import MatchupFighter, calculate_matchup


def fighter(identifier: int, name: str, **changes: Any) -> MatchupFighter:
    baseline = MatchupFighter(
        fighter_id=UUID(int=identifier),
        name=name,
        overall_rating=1500,
        striking_offence=50,
        striking_defence=50,
        wrestling_offence=50,
        takedown_defence=50,
        submission_threat=50,
        submission_defence=50,
        cardio=50,
        durability=50,
        power=50,
        pace=50,
        recent_form=50,
        strength_of_schedule=50,
        pressure=50,
        defensive_movement=50,
        knockdown_rate=50,
        grappling_control=50,
        getup_score=50,
        confidence=0.8,
    )
    return replace(baseline, **changes)


def test_direct_advantages_return_direction_difference_and_explanation() -> None:
    result = calculate_matchup(
        fighter(1, "Ari Vale", overall_rating=1580, striking_offence=75, striking_defence=65),
        fighter(2, "Bo North", overall_rating=1500, striking_offence=50, striking_defence=50),
    )

    assert result.advantages["overall"].fighter == "fighter_a"
    assert result.advantages["overall"].difference == 8
    assert result.advantages["striking"].difference == 20
    assert "Ari Vale" in result.advantages["striking"].explanation


def test_interaction_rules_compare_both_fighters_offence_and_defence() -> None:
    result = calculate_matchup(
        fighter(
            1,
            "Ari Vale",
            wrestling_offence=90,
            takedown_defence=80,
            power=90,
            knockdown_rate=80,
            submission_threat=85,
            grappling_control=80,
            pressure=85,
            cardio=85,
        ),
        fighter(
            2,
            "Bo North",
            wrestling_offence=40,
            takedown_defence=35,
            durability=35,
            striking_defence=40,
            submission_defence=35,
            getup_score=35,
            cardio=45,
            defensive_movement=40,
        ),
    )

    assert len(result.key_interactions) == 4
    assert all(interaction.advantage == "fighter_a" for interaction in result.key_interactions)
    assert all(0 <= interaction.strength <= 1 for interaction in result.key_interactions)
    assert all(interaction.explanation for interaction in result.key_interactions)


def test_equal_profiles_are_neutral() -> None:
    result = calculate_matchup(fighter(1, "Ari"), fighter(2, "Bo"))

    assert all(advantage.fighter == "neutral" for advantage in result.advantages.values())
    assert all(interaction.advantage == "neutral" for interaction in result.key_interactions)


def test_reversing_fighters_reverses_numerical_advantages() -> None:
    a = fighter(1, "Ari", overall_rating=1600, cardio=80, durability=70)
    b = fighter(2, "Bo", overall_rating=1450, cardio=40, durability=45)

    forward = calculate_matchup(a, b)
    reverse = calculate_matchup(b, a)

    for category in forward.advantages:
        assert forward.advantages[category].difference == pytest.approx(-reverse.advantages[category].difference)


def test_matchup_confidence_is_not_presented_as_prediction_probability() -> None:
    result = calculate_matchup(fighter(1, "Ari", confidence=0.9), fighter(2, "Bo", confidence=0.3))

    assert result.confidence == pytest.approx(0.6)
    assert result.confidence_category == "moderate"
    assert result.limitations == ("Limited data confidence for Bo",)


def test_self_matchup_is_rejected() -> None:
    same = fighter(1, "Ari")
    with pytest.raises(ValueError, match="themselves"):
        calculate_matchup(same, same)
