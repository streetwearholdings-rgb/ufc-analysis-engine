from uuid import UUID

from pydantic import BaseModel, Field


class MatchupFighterResponse(BaseModel):
    fighter_id: UUID
    name: str
    profile: dict[str, float]
    ratings: dict[str, float]
    style_scores: dict[str, float]
    recent_form: dict[str, float]


class AdvantageResponse(BaseModel):
    fighter: str
    difference: float
    explanation: str


class KeyInteractionResponse(BaseModel):
    factor: str
    advantage: str
    strength: float = Field(ge=0, le=1)
    difference: float
    explanation: str


class MatchupConfidenceResponse(BaseModel):
    overall: float = Field(ge=0, le=1)
    category: str
    limitations: list[str]


class MatchupResponse(BaseModel):
    fighter_a: MatchupFighterResponse
    fighter_b: MatchupFighterResponse
    comparison: dict[str, AdvantageResponse]
    key_interactions: list[KeyInteractionResponse]
    confidence: MatchupConfidenceResponse
    model_version: str
