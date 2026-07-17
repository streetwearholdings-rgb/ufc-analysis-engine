from datetime import date
from uuid import UUID

from pydantic import BaseModel, Field


class StyleScoreResponse(BaseModel):
    raw_value: float
    score: float = Field(ge=0, le=100)
    confidence: float = Field(ge=0, le=1)
    contributing_features: dict[str, float]
    explanation: str


class FighterStyleResponse(BaseModel):
    fighter_id: UUID
    calculation_date: date
    weight_class: str
    scores: dict[str, StyleScoreResponse]
    archetypes: dict[str, float]
    confidence_score: float = Field(ge=0, le=1, description="Data quality, not prediction probability")
    model_version: str
