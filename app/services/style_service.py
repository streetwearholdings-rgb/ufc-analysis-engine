from app.calculations.style_scores import StyleScore, classify_archetypes
from app.database.models.fighter_style_score import FighterStyleScore
from app.schemas.style import FighterStyleResponse, StyleScoreResponse

STYLE_FIELDS = (
    "pressure_striking",
    "counter_striking",
    "striking_power",
    "striking_volume",
    "defensive_movement",
    "wrestling_pressure",
    "grappling_control",
    "submission_threat",
    "takedown_defence",
    "scramble_ability",
    "cardio",
    "durability",
    "pace_sustainability",
)


def stored_style_response(row: FighterStyleScore) -> FighterStyleResponse:
    calculated: dict[str, StyleScore] = {}
    response_scores: dict[str, StyleScoreResponse] = {}
    for name in STYLE_FIELDS:
        value = float(getattr(row, name))
        explanation = f"Stored {name.replace('_', ' ')} percentile score for the fighter's weight class."
        calculated[name] = StyleScore(value, value, row.confidence_score, {}, explanation)
        response_scores[name] = StyleScoreResponse(
            raw_value=value,
            score=value,
            confidence=row.confidence_score,
            contributing_features={},
            explanation=explanation,
        )
    return FighterStyleResponse(
        fighter_id=row.fighter_id,
        calculation_date=row.calculation_date,
        weight_class=row.weight_class,
        scores=response_scores,
        archetypes=classify_archetypes(calculated),
        confidence_score=row.confidence_score,
        model_version=row.model_version,
    )
