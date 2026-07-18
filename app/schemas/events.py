from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class FighterSummary(BaseModel):
    fighter_id: UUID
    name: str
    nickname: str | None
    weight_class: str | None


class FightSummary(BaseModel):
    fight_id: UUID
    event_id: UUID
    weight_class: str | None
    scheduled_rounds: int | None
    status: str
    fighter_a: FighterSummary
    fighter_b: FighterSummary


class EventSummary(BaseModel):
    event_id: UUID
    name: str
    event_date: date
    location: str | None
    promotion: str
    fight_count: int


class EventFightCard(BaseModel):
    event: EventSummary
    fights: list[FightSummary]


class ContextSignalSummary(BaseModel):
    signal_id: UUID
    fighter_id: UUID
    fight_id: UUID | None
    category: str
    label: str
    direction: str
    review_status: str
    confidence: Decimal
    severity: Decimal
    occurred_at: datetime


class PendingContextPage(BaseModel):
    items: list[ContextSignalSummary]
    total: int
    limit: int
    offset: int


class ProbabilitySummary(BaseModel):
    fighter_id: UUID
    base_probability: Decimal = Field(ge=0, le=1)
    context_adjusted_probability: Decimal = Field(ge=0, le=1)


class MarketSummary(BaseModel):
    fighter_id: UUID
    bookmaker: str
    decimal_odds: Decimal
    market_probability: Decimal
    expected_value: Decimal
    bookmaker_count: int
    bookmaker_last_update: datetime


class ConsolidatedFightAnalysis(BaseModel):
    fight: FightSummary
    fighters: list[FighterSummary]
    probabilities: list[ProbabilitySummary]
    model_confidence: Decimal = Field(ge=0, le=1)
    best_bookmaker_odds: list[MarketSummary]
    applied_context_signals: list[dict[str, object]]
    excluded_context_signals: list[dict[str, object]]
    pending_context_signals: list[ContextSignalSummary]
    data_quality_warnings: list[str]
    prediction_timestamp: datetime
    model_version: str
    context_engine_version: str
    odds_timestamp: datetime | None


class ReviewRequest(BaseModel):
    reviewer: str = Field(min_length=1, max_length=200)
    reason: str = Field(min_length=1, max_length=2000)


class ReviewResponse(BaseModel):
    signal_id: UUID
    review_status: str
    reviewed_at: datetime
