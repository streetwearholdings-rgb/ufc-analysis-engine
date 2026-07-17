from dataclasses import dataclass

from app.calculations.normalization import percentile_rank, shrink_toward_midpoint


@dataclass(frozen=True, slots=True)
class StyleFeatures:
    fights_count: int
    strike_attempts_per_minute: float = 0.0
    strike_differential_per_minute: float = 0.0
    opponent_output_suppression: float = 0.0
    knockdowns_per_15: float = 0.0
    significant_strikes_landed_per_minute: float = 0.0
    striking_defence: float = 0.0
    takedown_attempts_per_15: float = 0.0
    takedowns_landed_per_15: float = 0.0
    control_seconds_per_15: float = 0.0
    submission_attempts_per_15: float = 0.0
    takedown_defence: float = 0.0
    reversals_per_15: float = 0.0
    late_round_output_ratio: float = 0.0
    knockdowns_absorbed_per_15: float = 0.0
    finish_loss_rate: float = 0.0
    output_consistency: float = 0.0


@dataclass(frozen=True, slots=True)
class StyleScore:
    raw_value: float
    score: float
    confidence: float
    contributing_features: dict[str, float]
    explanation: str


@dataclass(frozen=True, slots=True)
class StyleProfile:
    scores: dict[str, StyleScore]
    archetypes: dict[str, float]


STYLE_FORMULAS: dict[str, dict[str, float]] = {
    "pressure_striking": {
        "strike_attempts_per_minute": 0.5,
        "strike_differential_per_minute": 0.3,
        "opponent_output_suppression": 0.2,
    },
    "counter_striking": {
        "strike_differential_per_minute": 0.45,
        "striking_defence": 0.4,
        "strike_attempts_per_minute": -0.15,
    },
    "striking_power": {
        "knockdowns_per_15": 0.7,
        "finish_loss_rate": -0.1,
        "significant_strikes_landed_per_minute": 0.2,
    },
    "striking_volume": {"strike_attempts_per_minute": 0.65, "significant_strikes_landed_per_minute": 0.35},
    "defensive_movement": {"striking_defence": 0.7, "opponent_output_suppression": 0.3},
    "wrestling_pressure": {"takedown_attempts_per_15": 0.6, "takedowns_landed_per_15": 0.4},
    "grappling_control": {"control_seconds_per_15": 0.65, "takedowns_landed_per_15": 0.35},
    "submission_threat": {"submission_attempts_per_15": 0.75, "control_seconds_per_15": 0.25},
    "takedown_defence": {"takedown_defence": 1.0},
    "scramble_ability": {"reversals_per_15": 0.7, "takedown_defence": 0.3},
    "cardio": {"late_round_output_ratio": 0.7, "output_consistency": 0.3},
    "durability": {"knockdowns_absorbed_per_15": -0.6, "finish_loss_rate": -0.4},
    "pace_sustainability": {"late_round_output_ratio": 0.55, "output_consistency": 0.45},
}


def calculate_style_profile(
    fighter: StyleFeatures,
    weight_class_cohort: list[StyleFeatures],
    *,
    data_confidence: float,
    minimum_fights: int = 5,
    minimum_cohort: int = 10,
) -> StyleProfile:
    raw = _raw_values(fighter)
    cohort_raw = [_raw_values(member) for member in weight_class_cohort]
    sample_reliability = min(1.0, fighter.fights_count / max(minimum_fights, 1))
    cohort_reliability = min(1.0, len(weight_class_cohort) / max(minimum_cohort, 1))
    confidence = min(1.0, max(0.0, data_confidence)) * sample_reliability * cohort_reliability
    scores: dict[str, StyleScore] = {}
    for name, formula in STYLE_FORMULAS.items():
        percentile = percentile_rank(raw[name], [member[name] for member in cohort_raw])
        normalized = shrink_toward_midpoint(percentile, confidence)
        contributors = {feature: float(getattr(fighter, feature)) for feature in formula}
        scores[name] = StyleScore(
            raw[name],
            normalized,
            confidence,
            contributors,
            _explanation(name, normalized, formula),
        )
    return StyleProfile(scores, classify_archetypes(scores))


def classify_archetypes(scores: dict[str, StyleScore]) -> dict[str, float]:
    value = {name: score.score / 100 for name, score in scores.items()}
    candidates = {
        "pressure_striker": _mean(value["pressure_striking"], value["striking_volume"]),
        "counter_striker": _mean(value["counter_striking"], value["defensive_movement"]),
        "power_boxer": _mean(value["striking_power"], value["durability"]),
        "volume_kickboxer": _mean(value["striking_volume"], value["pace_sustainability"]),
        "outside_striker": _mean(value["defensive_movement"], value["counter_striking"]),
        "wrestling_controller": _mean(value["wrestling_pressure"], value["grappling_control"]),
        "chain_wrestler": _mean(value["wrestling_pressure"], value["cardio"]),
        "submission_hunter": _mean(value["submission_threat"], value["grappling_control"]),
        "scramble_grappler": _mean(value["scramble_ability"], value["submission_threat"]),
        "balanced_mixed_martial_artist": sum(value.values()) / len(value),
        "low_output_opportunist": _mean(1 - value["striking_volume"], value["striking_power"]),
        "fast_starter": _mean(value["striking_power"], 1 - value["cardio"]),
        "late_round_attritional_fighter": _mean(
            value["pressure_striking"], value["cardio"], value["pace_sustainability"]
        ),
    }
    return dict(sorted(candidates.items(), key=lambda item: (-item[1], item[0]))[:3])


def _raw_values(features: StyleFeatures) -> dict[str, float]:
    return {
        name: sum(float(getattr(features, feature)) * weight for feature, weight in formula.items())
        for name, formula in STYLE_FORMULAS.items()
    }


def _explanation(name: str, score: float, formula: dict[str, float]) -> str:
    level = "above-average" if score >= 60 else "below-average" if score <= 40 else "near-average"
    drivers = ", ".join(feature.replace("_", " ") for feature in formula)
    return f"{name.replace('_', ' ').title()} is {level}, driven by {drivers}."


def _mean(*values: float) -> float:
    return sum(values) / len(values)
