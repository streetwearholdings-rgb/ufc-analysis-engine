from datetime import date
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class FighterRatingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    fighter_id: UUID
    rating_date: date
    weight_class: str
    overall_rating: float
    striking_rating: float
    wrestling_rating: float
    submission_rating: float
    defensive_rating: float
    five_round_rating: float
    performance_score: float = Field(ge=0, le=100)
    confidence_score: float = Field(ge=0, le=1)
    sample_size: int = Field(ge=0)
    model_version: str
