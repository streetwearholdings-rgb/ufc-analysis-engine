from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class FighterReference(BaseModel):
    fighter_id: UUID
    name: str


class AnalysisResponse(BaseModel):
    fight_id: UUID
    event_id: UUID
    event_name: str
    scheduled_at: date
    fighter_a: FighterReference
    fighter_b: FighterReference
    predicted_winner: FighterReference | None
    predicted_loser: FighterReference | None
    model_probability: Decimal | None
    opponent_probability: Decimal | None
    market_probability: Decimal | None
    no_vig_market_probability: Decimal | None
    decimal_odds: Decimal | None
    value_edge: Decimal | None
    expected_value: Decimal | None
    confidence_score: Decimal | None
    confidence_tier: str
    feature_quality_score: Decimal | None
    risk_level: str
    recommendation: str
    recommendation_status: str
    no_bet_reason: str | None
    recommended_market: str | None
    rationale: str
    key_advantages: list[dict[str, object]]
    key_risks: list[str]
    warnings: list[str]
    model_type: str
    model_version: str
    probability_method: str
    calibration_status: str
    generated_at: datetime
    odds_updated_at: datetime | None


class AnalysisPage(BaseModel):
    items: list[AnalysisResponse]
    total: int
    limit: int
    offset: int


class AnalysisRunRequest(BaseModel):
    event_id: UUID | None = None
    force: bool = False


class AnalysisRunSummary(BaseModel):
    run_id: UUID
    model_type: str
    model_version: str
    events_processed: int
    fights_found: int
    fights_analysed: int
    recommendations_created: int
    no_bets: int
    insufficient_data: int
    failed: int
    started_at: datetime
    completed_at: datetime


class AnalysisStatusResponse(BaseModel):
    latest_run: UUID | None = None
    run_status: str = "never_run"
    model_type: str
    model_version: str
    fights_analysed: int = 0
    recommendations_created: int = 0
    failures: int = 0
    safe_error_summary: str | None = None
    latest_analysis_timestamp: datetime | None = None


class ModelStatusResponse(BaseModel):
    model_type: str
    model_version: str
    probability_method: str
    calibration_status: str
    latest_run: datetime | None
    latest_success: datetime | None
    upcoming_fights_analysed: int
    data_freshness: datetime | None
    odds_freshness: datetime | None


class AnalysisFilters(BaseModel):
    event_id: UUID | None = None
    minimum_confidence: Decimal | None = Field(default=None, ge=0, le=1)
    minimum_value_edge: Decimal | None = None
    recommendation_status: str | None = None
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)
