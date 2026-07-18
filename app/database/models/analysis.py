from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import JSON, Boolean, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, UUIDPrimaryKeyMixin


class AnalysisRun(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "analysis_runs"

    status: Mapped[str] = mapped_column(String(20), index=True)
    model_type: Mapped[str] = mapped_column(String(80))
    model_version: Mapped[str] = mapped_column(String(50), index=True)
    probability_method: Mapped[str] = mapped_column(String(120))
    calibration_status: Mapped[str] = mapped_column(String(40))
    event_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("events.id"), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    events_processed: Mapped[int] = mapped_column(Integer, default=0)
    fights_found: Mapped[int] = mapped_column(Integer, default=0)
    fights_analysed: Mapped[int] = mapped_column(Integer, default=0)
    recommendations_created: Mapped[int] = mapped_column(Integer, default=0)
    no_bets: Mapped[int] = mapped_column(Integer, default=0)
    insufficient_data: Mapped[int] = mapped_column(Integer, default=0)
    failed: Mapped[int] = mapped_column(Integer, default=0)
    error_summary: Mapped[str | None] = mapped_column(Text)


class FightAnalysis(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "fight_analyses"
    __table_args__ = (
        Index("ix_fight_analyses_fight_generated", "fight_id", "generated_at"),
        Index("ix_fight_analyses_status_active", "recommendation_status", "active"),
    )

    run_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("analysis_runs.id"), index=True)
    fight_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("fights.id"), index=True)
    event_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("events.id"), index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    scheduled_at: Mapped[date] = mapped_column(Date)
    fighter_a_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("fighters.id"))
    fighter_b_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("fighters.id"))
    predicted_winner_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("fighters.id"))
    predicted_loser_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("fighters.id"))
    model_probability: Mapped[Decimal | None] = mapped_column(Numeric(12, 8))
    opponent_probability: Mapped[Decimal | None] = mapped_column(Numeric(12, 8))
    market_probability: Mapped[Decimal | None] = mapped_column(Numeric(12, 8))
    no_vig_market_probability: Mapped[Decimal | None] = mapped_column(Numeric(12, 8))
    decimal_odds: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    value_edge: Mapped[Decimal | None] = mapped_column(Numeric(12, 8))
    expected_value: Mapped[Decimal | None] = mapped_column(Numeric(12, 8))
    confidence_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    confidence_tier: Mapped[str] = mapped_column(String(30))
    feature_quality_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    risk_level: Mapped[str] = mapped_column(String(30))
    recommendation: Mapped[str] = mapped_column(String(30))
    recommendation_status: Mapped[str] = mapped_column(String(30), index=True)
    recommended_side_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("fighters.id"))
    recommended_market: Mapped[str | None] = mapped_column(String(30))
    no_bet_reason: Mapped[str | None] = mapped_column(Text)
    odds_snapshot_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("odds_snapshots.id"))
    odds_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    data_freshness_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rationale: Mapped[str] = mapped_column(Text)
    key_advantages: Mapped[list[dict[str, object]]] = mapped_column(JSON)
    key_risks: Mapped[list[str]] = mapped_column(JSON)
    warnings: Mapped[list[str]] = mapped_column(JSON)
    model_type: Mapped[str] = mapped_column(String(80))
    model_version: Mapped[str] = mapped_column(String(50), index=True)
    probability_method: Mapped[str] = mapped_column(String(120))
    calibration_status: Mapped[str] = mapped_column(String(40))
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
