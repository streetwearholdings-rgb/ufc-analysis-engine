from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ConfidenceInput:
    fights_count: int
    rounds_count: int
    days_since_last_fight: int
    weight_class_relevance: float
    data_completeness: float
    statistical_consistency: float
    opponent_sample_quality: float
    missing_field_ratio: float = 0.0


@dataclass(frozen=True, slots=True)
class ConfidenceResult:
    score: float
    category: str
    limitations: tuple[str, ...]
    factors: dict[str, float]


def calculate_confidence(inputs: ConfidenceInput) -> ConfidenceResult:
    fights = _clamp(inputs.fights_count / 8)
    rounds = _clamp(inputs.rounds_count / 20)
    recency = _clamp(1 - max(inputs.days_since_last_fight - 180, 0) / 1460)
    relevance = _clamp(inputs.weight_class_relevance)
    completeness = _clamp(inputs.data_completeness) * (1 - _clamp(inputs.missing_field_ratio))
    consistency = _clamp(inputs.statistical_consistency)
    opponent_quality = _clamp(inputs.opponent_sample_quality)
    factors = {
        "fight_sample": fights,
        "round_sample": rounds,
        "recency": recency,
        "weight_class_relevance": relevance,
        "data_completeness": completeness,
        "statistical_consistency": consistency,
        "opponent_sample_quality": opponent_quality,
    }
    weights = {
        "fight_sample": 0.20,
        "round_sample": 0.10,
        "recency": 0.15,
        "weight_class_relevance": 0.15,
        "data_completeness": 0.15,
        "statistical_consistency": 0.10,
        "opponent_sample_quality": 0.15,
    }
    score = sum(factors[name] * weight for name, weight in weights.items())
    limitations: list[str] = []
    if inputs.fights_count < 3:
        limitations.append("small fight sample")
    if inputs.days_since_last_fight > 730:
        limitations.append("long inactivity")
    if completeness < 0.7:
        limitations.append("incomplete statistics")
    if relevance < 0.6:
        limitations.append("limited weight-class relevance")
    return ConfidenceResult(score, confidence_category(score), tuple(limitations), factors)


def confidence_category(score: float) -> str:
    if score >= 0.8:
        return "high"
    if score >= 0.6:
        return "moderate"
    if score >= 0.4:
        return "low"
    return "insufficient"


def _clamp(value: float) -> float:
    return min(1.0, max(0.0, value))
