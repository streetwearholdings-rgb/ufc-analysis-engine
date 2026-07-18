from datetime import datetime

from pydantic import BaseModel, Field


class UpcomingIngestionSummary(BaseModel):
    provider: str = "the_odds_api"
    events_processed: int = 0
    fights_processed: int = 0
    fighters_processed: int = 0
    odds_processed: int = 0
    records: dict[str, int] = Field(default_factory=dict)
    started_at: datetime
    completed_at: datetime


class IngestionStatusResponse(BaseModel):
    provider: str = "the_odds_api"
    running: bool = False
    last_successful_ingestion_time: datetime | None = None
    last_failure_time: datetime | None = None
    records_processed: dict[str, int] = Field(default_factory=dict)
    safe_error_summary: str | None = None
