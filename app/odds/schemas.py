from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProviderOutcome(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str
    price: Decimal = Field(gt=0)
    point: Decimal | None = None


class ProviderMarket(BaseModel):
    model_config = ConfigDict(extra="ignore")
    key: str
    last_update: datetime
    outcomes: list[ProviderOutcome] = Field(default_factory=list)

    @field_validator("last_update")
    @classmethod
    def timezone_required(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("provider timestamps must include a timezone")
        return value


class ProviderBookmaker(BaseModel):
    model_config = ConfigDict(extra="ignore")
    key: str
    title: str
    last_update: datetime
    markets: list[ProviderMarket] = Field(default_factory=list)


class ProviderEvent(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)
    provider_event_id: str = Field(alias="id")
    sport_key: str
    sport_title: str
    commence_time: datetime
    home_team: str
    away_team: str
    bookmakers: list[ProviderBookmaker] = Field(default_factory=list)

    @field_validator("commence_time")
    @classmethod
    def timezone_required(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("provider timestamps must include a timezone")
        return value


class QuotaMetadata(BaseModel):
    requests_remaining: int | None = None
    requests_used: int | None = None
    last_request_cost: int | None = None


class NormalisedOddsSnapshot(BaseModel):
    provider: str = "the_odds_api"
    provider_event_id: str
    internal_event_id: UUID | None
    internal_fight_id: UUID | None
    internal_fighter_id: UUID | None
    sport_key: str
    commence_time: datetime
    bookmaker_key: str
    bookmaker_name: str
    market_type: str = "moneyline"
    selection_name: str
    decimal_odds: Decimal = Field(gt=0)
    implied_probability: Decimal
    bookmaker_last_update: datetime
    captured_at: datetime


class OddsIngestionSummary(BaseModel):
    provider_events_received: int = 0
    provider_events_matched: int = 0
    provider_events_unmatched: int = 0
    bookmaker_markets_processed: int = 0
    snapshots_inserted: int = 0
    duplicate_snapshots_skipped: int = 0
    invalid_records_skipped: int = 0
    requests_remaining: int | None = None
    requests_used: int | None = None
    last_request_cost: int | None = None
    started_at: datetime
    completed_at: datetime


class MarketSelectionOdds(BaseModel):
    fighter_id: UUID
    fighter_name: str
    best_decimal_odds: Decimal
    best_bookmaker: str
    raw_implied_probability: Decimal
    bookmaker_last_update: datetime
    age_seconds: int
    bookmaker_count: int


class FightMarketOdds(BaseModel):
    fight_id: UUID
    selections: list[MarketSelectionOdds]
