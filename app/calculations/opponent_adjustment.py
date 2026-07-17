from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True, slots=True)
class HistoricalOpponentMetric:
    as_of: date
    average_allowed: float
    fights_count: int


@dataclass(frozen=True, slots=True)
class OpponentAdjustment:
    raw_value: float
    adjusted_value: float
    shrunk_opponent_baseline: float
    sample_confidence: float
    meets_minimum_sample: bool


def adjust_offensive_output(
    fighter_output: float,
    opponent_history: HistoricalOpponentMetric,
    division_average_allowed: float,
    *,
    fight_date: date,
    minimum_fights: int = 3,
    denominator_floor: float = 1e-6,
) -> OpponentAdjustment:
    _validate_inputs(opponent_history, fight_date, minimum_fights, denominator_floor)
    confidence = _sample_confidence(opponent_history.fights_count, minimum_fights)
    baseline = _shrink(opponent_history.average_allowed, division_average_allowed, confidence)
    denominator = max(abs(baseline), denominator_floor)
    adjusted = fighter_output / denominator * division_average_allowed
    return OpponentAdjustment(
        fighter_output,
        adjusted,
        baseline,
        confidence,
        opponent_history.fights_count >= minimum_fights,
    )


def calculate_defensive_suppression(
    opponent_actual_output: float,
    opponent_expected_history: HistoricalOpponentMetric,
    division_average_output: float,
    *,
    fight_date: date,
    minimum_fights: int = 3,
) -> OpponentAdjustment:
    _validate_inputs(opponent_expected_history, fight_date, minimum_fights, 1e-6)
    confidence = _sample_confidence(opponent_expected_history.fights_count, minimum_fights)
    expected = _shrink(opponent_expected_history.average_allowed, division_average_output, confidence)
    suppression = expected - opponent_actual_output
    return OpponentAdjustment(
        opponent_actual_output,
        suppression,
        expected,
        confidence,
        opponent_expected_history.fights_count >= minimum_fights,
    )


def _sample_confidence(fights_count: int, minimum_fights: int) -> float:
    if minimum_fights == 0:
        return 1.0
    return min(1.0, max(0.0, fights_count / minimum_fights))


def _shrink(observed: float, division_average: float, confidence: float) -> float:
    return observed * confidence + division_average * (1.0 - confidence)


def _validate_inputs(
    history: HistoricalOpponentMetric,
    fight_date: date,
    minimum_fights: int,
    denominator_floor: float,
) -> None:
    if history.as_of >= fight_date:
        raise ValueError("opponent history must contain only information available before the fight")
    if history.fights_count < 0 or minimum_fights < 0:
        raise ValueError("fight counts cannot be negative")
    if denominator_floor <= 0:
        raise ValueError("denominator_floor must be positive")
