from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from app.context.enums import ClaimType, ContextCategory, ContextLabel, Direction, ExtractionMethod, SourceType
from app.context.registry import CONTEXT_LABEL_REGISTRY


class ContextSourceInput(BaseModel):
    source_type: SourceType
    publisher: str
    author: str | None = None
    url: str | None = None
    title: str
    published_at: datetime
    captured_at: datetime
    reliability_override: Decimal | None = Field(default=None, ge=0, le=1)
    is_primary_source: bool = False

    @field_validator("published_at", "captured_at")
    @classmethod
    def aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("context timestamps must be timezone-aware")
        return value

    @model_validator(mode="after")
    def publication_precedes_capture(self) -> "ContextSourceInput":
        if self.published_at > self.captured_at:
            raise ValueError("published_at cannot be after captured_at")
        return self


class ContextSignalInput(BaseModel):
    fighter_id: UUID
    fight_id: UUID | None = None
    event_id: UUID | None = None
    category: ContextCategory
    label: ContextLabel
    direction: Direction
    severity: Decimal = Field(ge=0, le=1)
    confidence: Decimal = Field(ge=0, le=1)
    occurred_at: datetime
    expires_at: datetime | None = None
    claim_type: ClaimType
    extraction_method: ExtractionMethod = ExtractionMethod.MANUAL
    notes: str | None = None
    measurable_value: Decimal | None = None

    @model_validator(mode="after")
    def validate_signal(self) -> "ContextSignalInput":
        if self.label not in CONTEXT_LABEL_REGISTRY[self.category]:
            raise ValueError(f"{self.label.value} is not valid for {self.category.value}")
        if self.expires_at is not None and self.expires_at <= self.occurred_at:
            raise ValueError("expires_at must be after occurred_at")
        if self.label in FIGHT_SPECIFIC_LABELS and self.fight_id is None:
            raise ValueError(f"fight_id is required for {self.label.value}")
        if self.occurred_at.tzinfo is None or (self.expires_at and self.expires_at.tzinfo is None):
            raise ValueError("context timestamps must be timezone-aware")
        return self


class LlmExtractedContext(BaseModel):
    fighter_name: str
    fight_reference: str
    category: ContextCategory
    label: ContextLabel
    direction: Direction
    severity: Decimal = Field(ge=0, le=1)
    confidence: Decimal = Field(ge=0, le=1)
    claim_type: ClaimType
    occurred_at: datetime
    supporting_text: str = Field(min_length=1)
    requires_review: bool = True

    @model_validator(mode="after")
    def valid_pair(self) -> "LlmExtractedContext":
        if self.label not in CONTEXT_LABEL_REGISTRY[self.category]:
            raise ValueError("invalid context category-label combination")
        return self


class WeightedContextSignal(BaseModel):
    signal_id: UUID
    category: ContextCategory
    label: ContextLabel
    direction: Direction
    severity: Decimal
    confidence: Decimal
    source_reliability: Decimal
    age_days: Decimal
    recency_weight: Decimal
    weighted_score: Decimal


class ContextFeatureSet(BaseModel):
    fighter_id: UUID
    fight_id: UUID
    as_of_time: datetime
    context_version: str
    values: dict[str, Decimal | None]
    source_signal_ids: dict[str, list[UUID]]


class ContextualPrediction(BaseModel):
    fighter_id: UUID
    fight_id: UUID
    base_probability: Decimal
    raw_context_score: Decimal
    requested_adjustment: Decimal
    applied_adjustment: Decimal
    final_probability: Decimal
    context_confidence: Decimal
    signals_used: list[UUID]
    signals_excluded: list[dict[str, str]]
    warnings: list[str]
    explanation_items: list[dict[str, object]]


class ContextualFightPrediction(BaseModel):
    fight_id: UUID
    fighter_a: ContextualPrediction
    fighter_b: ContextualPrediction
    calculation_version: str
    as_of_time: datetime


FIGHT_SPECIFIC_LABELS = {
    ContextLabel.MISSED_WEIGHT_CURRENT_FIGHT,
    ContextLabel.SHORT_NOTICE_REPLACEMENT,
    ContextLabel.SHORT_NOTICE_DAYS,
    ContextLabel.OPPONENT_CHANGED,
    ContextLabel.WEIGHT_CLASS_DEBUT,
    ContextLabel.ACTIVE_MEDICAL_SUSPENSION,
}
