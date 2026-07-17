from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PerformanceComponentResponse(BaseModel):
    score: float = Field(ge=0, le=100)
    explanation: str


class FightPerformanceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    fight_id: UUID
    fighter_id: UUID
    opponent_id: UUID
    damage: PerformanceComponentResponse
    striking: PerformanceComponentResponse
    grappling: PerformanceComponentResponse
    control: PerformanceComponentResponse
    result_quality: PerformanceComponentResponse
    raw_performance_score: float = Field(ge=0, le=100)
    opponent_adjusted_score: float = Field(ge=0, le=100)
    final_performance_score: float = Field(ge=0, le=100)
    model_version: str
    calculated_at: datetime
