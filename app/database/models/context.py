from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ContextSource(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "context_sources"
    __table_args__ = (CheckConstraint("reliability_score >= 0 AND reliability_score <= 1", name="valid_reliability"),)
    source_type: Mapped[str] = mapped_column(String(40), index=True)
    publisher: Mapped[str] = mapped_column(String(200))
    author: Mapped[str | None] = mapped_column(String(200))
    url: Mapped[str | None] = mapped_column(String(1000), unique=True)
    title: Mapped[str] = mapped_column(String(500))
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    reliability_score: Mapped[Decimal] = mapped_column(Numeric(5, 4))
    default_reliability_score: Mapped[Decimal] = mapped_column(Numeric(5, 4))
    reliability_overridden: Mapped[bool] = mapped_column(Boolean, default=False)
    is_primary_source: Mapped[bool] = mapped_column(Boolean, default=False)


class ContextDocument(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "context_documents"
    source_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("context_sources.id"), index=True)
    raw_text: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    language: Mapped[str] = mapped_column(String(20), default="en")
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ContextSignal(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "context_signals"
    __table_args__ = (
        CheckConstraint("severity >= 0 AND severity <= 1", name="valid_severity"),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="valid_confidence"),
        CheckConstraint("source_reliability >= 0 AND source_reliability <= 1", name="valid_source_reliability"),
        UniqueConstraint("deduplication_key"),
        Index("ix_context_signals_fighter_fight", "fighter_id", "fight_id"),
        Index("ix_context_signals_category_label", "category", "label"),
    )
    fighter_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("fighters.id"), index=True)
    fight_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("fights.id"), index=True)
    event_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("events.id"), index=True)
    category: Mapped[str] = mapped_column(String(40), index=True)
    label: Mapped[str] = mapped_column(String(60), index=True)
    direction: Mapped[str] = mapped_column(String(20))
    severity: Mapped[Decimal] = mapped_column(Numeric(5, 4))
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4))
    source_reliability: Mapped[Decimal] = mapped_column(Numeric(5, 4))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_status: Mapped[str] = mapped_column(String(20), index=True)
    claim_type: Mapped[str] = mapped_column(String(30))
    extraction_method: Mapped[str] = mapped_column(String(30))
    deduplication_key: Mapped[str] = mapped_column(String(64))
    notes: Mapped[str | None] = mapped_column(Text)
    numeric_value: Mapped[Decimal | None] = mapped_column(Numeric(16, 6))
    is_contradicted: Mapped[bool] = mapped_column(Boolean, default=False)


class ContextSignalSource(Base):
    __tablename__ = "context_signal_sources"
    __table_args__ = (UniqueConstraint("context_signal_id", "context_source_id"),)
    context_signal_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("context_signals.id"), primary_key=True)
    context_source_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("context_sources.id"), primary_key=True)
    supporting_text: Mapped[str] = mapped_column(Text)
    is_primary_support: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ContextReview(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "context_reviews"
    context_signal_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("context_signals.id"), index=True)
    reviewer: Mapped[str] = mapped_column(String(200))
    decision: Mapped[str] = mapped_column(String(20))
    reason: Mapped[str] = mapped_column(Text)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    previous_status: Mapped[str] = mapped_column(String(20))
    new_status: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ContextFeatureValue(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "context_feature_values"
    __table_args__ = (UniqueConstraint("fighter_id", "fight_id", "feature_name", "context_version"),)
    fighter_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("fighters.id"), index=True)
    fight_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("fights.id"), index=True)
    feature_name: Mapped[str] = mapped_column(String(80))
    numeric_value: Mapped[Decimal | None] = mapped_column(Numeric(16, 6))
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    context_version: Mapped[str] = mapped_column(String(60))
    source_signal_ids: Mapped[list[str]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ContextAdjustment(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "context_adjustments"
    __table_args__ = (
        CheckConstraint("base_probability >= 0 AND base_probability <= 1", name="valid_base_probability"),
        CheckConstraint("final_probability >= 0 AND final_probability <= 1", name="valid_final_probability"),
        Index("ix_context_adjustments_fight_calculated", "fight_id", "calculated_at"),
    )
    fighter_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("fighters.id"), index=True)
    fight_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("fights.id"), index=True)
    base_probability: Mapped[Decimal] = mapped_column(Numeric(12, 8))
    raw_context_score: Mapped[Decimal] = mapped_column(Numeric(12, 8))
    requested_adjustment: Mapped[Decimal] = mapped_column(Numeric(12, 8))
    applied_adjustment: Mapped[Decimal] = mapped_column(Numeric(12, 8))
    final_probability: Mapped[Decimal] = mapped_column(Numeric(12, 8))
    context_confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4))
    calculation_version: Mapped[str] = mapped_column(String(60))
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    explanation_json: Mapped[dict[str, object]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class FighterAlias(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "fighter_aliases"
    fighter_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("fighters.id"), index=True)
    alias: Mapped[str] = mapped_column(String(200))
    normalised_alias: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    source: Mapped[str] = mapped_column(String(200))
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
