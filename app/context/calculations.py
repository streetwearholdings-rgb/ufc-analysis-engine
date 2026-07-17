import math
from datetime import UTC, datetime
from decimal import Decimal

from app.context.enums import ContextCategory, Direction, ReviewStatus
from app.context.registry import HALF_LIFE_DAYS
from app.context.schemas import WeightedContextSignal
from app.database.models.context import ContextSignal

MULTIPLIERS = {
    Direction.POSITIVE: Decimal(1),
    Direction.NEGATIVE: Decimal(-1),
    Direction.NEUTRAL: Decimal(0),
    Direction.UNCERTAIN: Decimal(0),
}


def calculate_signal_age(occurred_at: datetime, as_of_time: datetime) -> Decimal:
    occurred = _utc(occurred_at)
    target = _utc(as_of_time)
    if occurred > target:
        raise ValueError("signal occurrence cannot be after as_of_time")
    return Decimal(str((target - occurred).total_seconds() / 86400))


def is_signal_expired(signal: ContextSignal, as_of_time: datetime) -> bool:
    return signal.expires_at is not None and _utc(signal.expires_at) <= _utc(as_of_time)


def calculate_recency_weight(
    category: ContextCategory,
    occurred_at: datetime,
    as_of_time: datetime,
    *,
    enabled: bool = True,
    expires_at: datetime | None = None,
) -> tuple[Decimal, Decimal]:
    age = calculate_signal_age(occurred_at, as_of_time)
    if expires_at is not None and _utc(expires_at) <= _utc(as_of_time):
        return age, Decimal(0)
    half_life = HALF_LIFE_DAYS[category]
    if not enabled or half_life is None:
        return age, Decimal(1)
    return age, Decimal(str(math.exp(-math.log(2) * float(age) / half_life)))


def calculate_weighted_context_score(
    signal: ContextSignal,
    as_of_time: datetime,
    *,
    status: ReviewStatus,
    recency_decay_enabled: bool = True,
    is_contradicted: bool | None = None,
) -> WeightedContextSignal:
    category = ContextCategory(signal.category)
    age, recency = calculate_recency_weight(
        category, signal.occurred_at, as_of_time, enabled=recency_decay_enabled, expires_at=signal.expires_at
    )
    direction = Direction(signal.direction)
    contradicted = signal.is_contradicted if is_contradicted is None else is_contradicted
    active = status == ReviewStatus.APPROVED and not contradicted
    score = (
        MULTIPLIERS[direction] * signal.severity * signal.confidence * signal.source_reliability * recency
        if active
        else Decimal(0)
    )
    return WeightedContextSignal(
        signal_id=signal.id,
        category=category,
        label=signal.label,
        direction=direction,
        severity=signal.severity,
        confidence=signal.confidence,
        source_reliability=signal.source_reliability,
        age_days=age,
        recency_weight=recency,
        weighted_score=score,
    )


def _utc(value: datetime) -> datetime:
    return value.astimezone(UTC) if value.tzinfo else value.replace(tzinfo=UTC)
