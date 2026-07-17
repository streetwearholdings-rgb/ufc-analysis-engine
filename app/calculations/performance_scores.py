from dataclasses import dataclass
from enum import StrEnum
from math import isclose


class PerformanceResult(StrEnum):
    WIN = "win"
    LOSS = "loss"
    DRAW = "draw"
    NO_CONTEST = "no_contest"


@dataclass(frozen=True, slots=True)
class PerformanceWeights:
    damage: float = 0.30
    striking: float = 0.20
    grappling: float = 0.20
    control: float = 0.15
    result_quality: float = 0.15

    def __post_init__(self) -> None:
        if min(self.damage, self.striking, self.grappling, self.control, self.result_quality) < 0:
            raise ValueError("performance weights cannot be negative")
        if not isclose(sum(self.as_tuple()), 1.0, abs_tol=1e-9):
            raise ValueError("performance weights must sum to 1")

    def as_tuple(self) -> tuple[float, ...]:
        return (self.damage, self.striking, self.grappling, self.control, self.result_quality)


@dataclass(frozen=True, slots=True)
class PerformanceInput:
    result: PerformanceResult
    knockdowns: int = 0
    significant_head_strikes: int = 0
    significant_strike_differential_per_minute: float = 0.0
    significant_strike_accuracy: float = 0.0
    defensive_avoidance: float = 0.0
    significant_strike_output_per_minute: float = 0.0
    opponent_adjusted_striking: float = 50.0
    takedowns_landed: int = 0
    takedown_accuracy: float = 0.0
    submission_attempts: int = 0
    reversals: int = 0
    control_differential_seconds: float = 0.0
    control_duration_seconds: float = 0.0
    significant_ground_strikes: int = 0
    activity_factor: float | None = None
    advancement_factor: float | None = None
    opponent_rating: float = 1500.0
    opponent_durability: float | None = None
    method: str | None = None
    finish_round: int | None = None
    scheduled_rounds: int = 3
    fighter_short_notice: bool = False
    opponent_short_notice: bool = False
    fighter_missed_weight: bool = False
    opponent_missed_weight: bool = False


@dataclass(frozen=True, slots=True)
class ScoreComponent:
    score: float
    features: dict[str, float | int | str]
    explanation: str


@dataclass(frozen=True, slots=True)
class PerformanceScore:
    damage: ScoreComponent
    striking: ScoreComponent
    grappling: ScoreComponent
    control: ScoreComponent
    result_quality: ScoreComponent
    raw_performance_score: float
    opponent_adjusted_score: float
    final_performance_score: float


def calculate_performance_score(
    inputs: PerformanceInput,
    weights: PerformanceWeights | None = None,
) -> PerformanceScore:
    weights = weights or PerformanceWeights()
    damage = _damage_score(inputs)
    striking = _striking_score(inputs)
    grappling = _grappling_score(inputs)
    control = _control_score(inputs)
    result_quality = _result_quality_score(inputs)
    raw = (
        damage.score * weights.damage
        + striking.score * weights.striking
        + grappling.score * weights.grappling
        + control.score * weights.control
        + result_quality.score * weights.result_quality
    )
    # Historical opponent adjustment is introduced in Milestone 4. Keeping the
    # separate field now makes that addition explicit and backwards compatible.
    return PerformanceScore(damage, striking, grappling, control, result_quality, raw, raw, raw)


def _damage_score(inputs: PerformanceInput) -> ScoreComponent:
    differential = _clamp(50 + inputs.significant_strike_differential_per_minute * 10)
    durability = inputs.opponent_durability if inputs.opponent_durability is not None else 50.0
    finish_bonus = 18.0 if inputs.result is PerformanceResult.WIN and _is_finish(inputs.method) else 0.0
    finish_bonus *= 1.0 + _clamp(durability, 0, 100) / 200.0
    score = _clamp(
        0.34 * _clamp(inputs.knockdowns * 35)
        + 0.23 * _clamp(inputs.significant_head_strikes * 2)
        + 0.28 * differential
        + finish_bonus
    )
    return ScoreComponent(
        score,
        {
            "knockdowns": inputs.knockdowns,
            "significant_head_strikes": inputs.significant_head_strikes,
            "strike_differential_per_minute": inputs.significant_strike_differential_per_minute,
            "finish_bonus": finish_bonus,
        },
        "Damage reflects knockdowns, head strikes, strike differential, and finish quality.",
    )


def _striking_score(inputs: PerformanceInput) -> ScoreComponent:
    score = _clamp(
        0.30 * _clamp(50 + inputs.significant_strike_differential_per_minute * 10)
        + 0.20 * _percent(inputs.significant_strike_accuracy)
        + 0.20 * _percent(inputs.defensive_avoidance)
        + 0.15 * _clamp(inputs.significant_strike_output_per_minute * 10)
        + 0.15 * _clamp(inputs.opponent_adjusted_striking)
    )
    return ScoreComponent(
        score,
        {
            "accuracy": inputs.significant_strike_accuracy,
            "defensive_avoidance": inputs.defensive_avoidance,
            "output_per_minute": inputs.significant_strike_output_per_minute,
            "opponent_adjusted_striking": inputs.opponent_adjusted_striking,
        },
        "Striking effectiveness combines differential, accuracy, avoidance, output, and opponent context.",
    )


def _grappling_score(inputs: PerformanceInput) -> ScoreComponent:
    score = _clamp(
        0.25 * _clamp(inputs.takedowns_landed * 25)
        + 0.25 * _percent(inputs.takedown_accuracy)
        + 0.20 * _clamp(inputs.submission_attempts * 30)
        + 0.10 * _clamp(inputs.reversals * 40)
        + 0.20 * _clamp(50 + inputs.control_differential_seconds / 6)
    )
    return ScoreComponent(
        score,
        {
            "takedowns_landed": inputs.takedowns_landed,
            "takedown_accuracy": inputs.takedown_accuracy,
            "submission_attempts": inputs.submission_attempts,
            "reversals": inputs.reversals,
            "control_differential_seconds": inputs.control_differential_seconds,
        },
        "Grappling effectiveness reflects takedowns, submissions, reversals, and control differential.",
    )


def _control_score(inputs: PerformanceInput) -> ScoreComponent:
    inferred_activity = _clamp(
        0.2 + inputs.significant_ground_strikes / 25 + inputs.submission_attempts / 5,
        0.0,
        1.0,
    )
    activity = _clamp(inputs.activity_factor if inputs.activity_factor is not None else inferred_activity, 0, 1)
    advancement = _clamp(inputs.advancement_factor if inputs.advancement_factor is not None else 0.5, 0, 1)
    effective_control = inputs.control_duration_seconds * activity * advancement
    score = _clamp(effective_control / 3)
    return ScoreComponent(
        score,
        {
            "control_duration_seconds": inputs.control_duration_seconds,
            "activity_factor": activity,
            "advancement_factor": advancement,
            "effective_control_seconds": effective_control,
        },
        "Control is rewarded only when duration is supported by inferred activity and advancement.",
    )


def _result_quality_score(inputs: PerformanceInput) -> ScoreComponent:
    base = {
        PerformanceResult.WIN: 55.0,
        PerformanceResult.LOSS: 25.0,
        PerformanceResult.DRAW: 40.0,
        PerformanceResult.NO_CONTEST: 50.0,
    }[inputs.result]
    opponent_quality = _clamp(50 + (inputs.opponent_rating - 1500) / 6)
    score = base * 0.55 + opponent_quality * 0.45
    if inputs.result is PerformanceResult.WIN and _is_finish(inputs.method):
        score += 8.0
        if inputs.finish_round:
            score += 5.0 * max(inputs.scheduled_rounds - inputs.finish_round, 0) / inputs.scheduled_rounds
    score += 4.0 if inputs.fighter_short_notice else 0.0
    score -= 4.0 if inputs.opponent_short_notice else 0.0
    score -= 5.0 if inputs.fighter_missed_weight else 0.0
    score += 3.0 if inputs.opponent_missed_weight else 0.0
    return ScoreComponent(
        _clamp(score),
        {
            "result": inputs.result.value,
            "opponent_rating": inputs.opponent_rating,
            "opponent_quality": opponent_quality,
            "scheduled_rounds": inputs.scheduled_rounds,
        },
        "Result quality accounts for outcome, opponent strength, finish timing, and bout context.",
    )


def _percent(value: float) -> float:
    return _clamp(value * 100)


def _clamp(value: float, minimum: float = 0.0, maximum: float = 100.0) -> float:
    return min(maximum, max(minimum, value))


def _is_finish(method: str | None) -> bool:
    return bool(method and "decision" not in method.lower())
