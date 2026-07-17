from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class MatchupFighter:
    fighter_id: UUID
    name: str
    overall_rating: float
    striking_offence: float
    striking_defence: float
    wrestling_offence: float
    takedown_defence: float
    submission_threat: float
    submission_defence: float
    cardio: float
    durability: float
    power: float
    pace: float
    recent_form: float
    strength_of_schedule: float
    pressure: float
    defensive_movement: float
    knockdown_rate: float
    grappling_control: float
    getup_score: float
    confidence: float


@dataclass(frozen=True, slots=True)
class Advantage:
    fighter: str
    difference: float
    explanation: str


@dataclass(frozen=True, slots=True)
class KeyInteraction:
    factor: str
    advantage: str
    strength: float
    difference: float
    explanation: str


@dataclass(frozen=True, slots=True)
class MatchupResult:
    advantages: dict[str, Advantage]
    key_interactions: tuple[KeyInteraction, ...]
    confidence: float
    confidence_category: str
    limitations: tuple[str, ...]


def calculate_matchup(fighter_a: MatchupFighter, fighter_b: MatchupFighter) -> MatchupResult:
    if fighter_a.fighter_id == fighter_b.fighter_id:
        raise ValueError("a fighter cannot be matched against themselves")
    differences = {
        "overall": _clamp((fighter_a.overall_rating - fighter_b.overall_rating) / 10, -100, 100),
        "striking": _mean_difference(
            (fighter_a.striking_offence, fighter_a.striking_defence),
            (fighter_b.striking_offence, fighter_b.striking_defence),
        ),
        "wrestling": fighter_a.wrestling_offence - fighter_b.wrestling_offence,
        "submission": fighter_a.submission_threat - fighter_b.submission_threat,
        "cardio": fighter_a.cardio - fighter_b.cardio,
        "durability": fighter_a.durability - fighter_b.durability,
        "power": fighter_a.power - fighter_b.power,
        "pace": fighter_a.pace - fighter_b.pace,
        "recent_form": fighter_a.recent_form - fighter_b.recent_form,
        "strength_of_schedule": fighter_a.strength_of_schedule - fighter_b.strength_of_schedule,
    }
    advantages = {
        name: Advantage(
            _side(difference),
            difference,
            _advantage_explanation(name, difference, fighter_a.name, fighter_b.name),
        )
        for name, difference in differences.items()
    }
    interactions = tuple(
        sorted(_interactions(fighter_a, fighter_b), key=lambda interaction: interaction.strength, reverse=True)
    )
    confidence = min(1.0, max(0.0, (fighter_a.confidence + fighter_b.confidence) / 2))
    limitations: list[str] = []
    if fighter_a.confidence < 0.6:
        limitations.append(f"Limited data confidence for {fighter_a.name}")
    if fighter_b.confidence < 0.6:
        limitations.append(f"Limited data confidence for {fighter_b.name}")
    return MatchupResult(advantages, interactions, confidence, _confidence_category(confidence), tuple(limitations))


def _interactions(a: MatchupFighter, b: MatchupFighter) -> list[KeyInteraction]:
    wrestling = ((a.wrestling_offence - b.takedown_defence) - (b.wrestling_offence - a.takedown_defence)) / 2
    knockout = (
        (a.power + a.knockdown_rate - b.durability - b.striking_defence)
        - (b.power + b.knockdown_rate - a.durability - a.striking_defence)
    ) / 4
    submission = (
        (a.submission_threat + a.grappling_control - b.submission_defence - b.getup_score)
        - (b.submission_threat + b.grappling_control - a.submission_defence - a.getup_score)
    ) / 4
    late_pressure = (
        (a.pressure + a.cardio - b.cardio - b.defensive_movement)
        - (b.pressure + b.cardio - a.cardio - a.defensive_movement)
    ) / 4
    return [
        _interaction("Wrestling offence versus takedown defence", wrestling, a, b),
        _interaction("Knockout threat versus durability and striking defence", knockout, a, b),
        _interaction("Submission threat versus submission defence and get-up ability", submission, a, b),
        _interaction("Late pressure versus cardio and defensive movement", late_pressure, a, b),
    ]


def _interaction(factor: str, difference: float, a: MatchupFighter, b: MatchupFighter) -> KeyInteraction:
    side = _side(difference)
    leader = a.name if side == "fighter_a" else b.name if side == "fighter_b" else "Neither fighter"
    return KeyInteraction(
        factor,
        side,
        min(1.0, abs(difference) / 50),
        difference,
        f"{leader} has the stronger {factor.lower()} interaction based on the opposing attributes.",
    )


def _side(difference: float) -> str:
    if difference > 1e-9:
        return "fighter_a"
    if difference < -1e-9:
        return "fighter_b"
    return "neutral"


def _advantage_explanation(name: str, difference: float, a_name: str, b_name: str) -> str:
    side = _side(difference)
    if side == "neutral":
        return f"The fighters are effectively even in {name.replace('_', ' ')}."
    leader = a_name if side == "fighter_a" else b_name
    return f"{leader} leads the {name.replace('_', ' ')} comparison by {abs(difference):.1f} points."


def _mean_difference(a_values: tuple[float, ...], b_values: tuple[float, ...]) -> float:
    return sum(a - b for a, b in zip(a_values, b_values, strict=True)) / len(a_values)


def _confidence_category(score: float) -> str:
    if score >= 0.8:
        return "high"
    if score >= 0.6:
        return "moderate"
    if score >= 0.4:
        return "low"
    return "insufficient"


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return min(maximum, max(minimum, value))
