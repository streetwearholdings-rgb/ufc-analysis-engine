import hashlib
import re
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.context.enums import (
    ClaimType,
    ContextLabel,
    ExtractionMethod,
    ReviewStatus,
)
from app.context.reliability import calculate_effective_source_reliability, get_default_source_reliability
from app.context.schemas import ContextSignalInput, ContextSourceInput
from app.database.models.context import ContextDocument, ContextReview, ContextSignal, ContextSource
from app.repositories.context import ContextRepository, utc_now

AUTO_LABELS = {
    ContextLabel.MISSED_WEIGHT_CURRENT_FIGHT,
    ContextLabel.SHORT_NOTICE_REPLACEMENT,
    ContextLabel.OPPONENT_CHANGED,
    ContextLabel.WEIGHT_CLASS_DEBUT,
    ContextLabel.WEIGHT_CLASS_MOVE_UP,
    ContextLabel.WEIGHT_CLASS_MOVE_DOWN,
    ContextLabel.ACTIVE_MEDICAL_SUSPENSION,
}
SUBJECTIVE_LABELS = {
    ContextLabel.TRAINING_INTERRUPTION,
    ContextLabel.NEW_TRAINING_CAMP,
    ContextLabel.NEW_HEAD_COACH,
    ContextLabel.CONTRACT_DISPUTE,
}


class ContextService:
    def __init__(self, session: Session, settings: Settings | None = None) -> None:
        self.session = session
        self.settings = settings or get_settings()
        self.repository = ContextRepository(session)

    def create_source(self, data: ContextSourceInput) -> ContextSource:
        default = get_default_source_reliability(data.source_type)
        effective = calculate_effective_source_reliability(data.source_type, data.reliability_override)
        return self.repository.save_source(
            ContextSource(
                source_type=data.source_type,
                publisher=data.publisher,
                author=data.author,
                url=data.url,
                title=data.title,
                published_at=data.published_at,
                captured_at=data.captured_at,
                reliability_score=effective,
                default_reliability_score=default,
                reliability_overridden=data.reliability_override is not None,
                is_primary_source=data.is_primary_source,
            )
        )

    def create_document(self, source_id: UUID, raw_text: str, *, language: str = "en") -> ContextDocument:
        source = self.session.get(ContextSource, source_id)
        if source is None:
            raise ValueError("context source does not exist")
        now = utc_now()
        return self.repository.save_document(
            ContextDocument(
                source_id=source_id,
                raw_text=raw_text,
                content_hash=hashlib.sha256(raw_text.encode()).hexdigest(),
                language=language,
                published_at=source.published_at,
                captured_at=source.captured_at,
                created_at=now,
            )
        )

    def create_signal(
        self,
        data: ContextSignalInput,
        *,
        source_id: UUID,
        supporting_text: str,
    ) -> tuple[ContextSignal, bool]:
        source = self.session.get(ContextSource, source_id)
        if source is None:
            raise ValueError("a valid context source is required")
        if data.occurred_at > source.captured_at:
            raise ValueError("occurred_at cannot be after source capture time")
        if data.extraction_method != ExtractionMethod.MANUAL and not supporting_text.strip():
            raise ValueError("supporting evidence is required for extracted signals")
        key = build_signal_deduplication_key(data)
        duplicate = self.repository.find_duplicate_signal(key)
        now = utc_now()
        if duplicate is not None:
            self.repository.attach_source(
                duplicate.id, source.id, supporting_text, primary=source.is_primary_source, now=now
            )
            if source.reliability_score > duplicate.source_reliability:
                duplicate.source_reliability = source.reliability_score
            return duplicate, False
        signal = self.repository.save_signal(
            ContextSignal(
                fighter_id=data.fighter_id,
                fight_id=data.fight_id,
                event_id=data.event_id,
                category=data.category,
                label=data.label,
                direction=data.direction,
                severity=data.severity,
                confidence=data.confidence,
                source_reliability=source.reliability_score,
                occurred_at=data.occurred_at,
                expires_at=data.expires_at,
                review_status=ReviewStatus.PENDING,
                claim_type=data.claim_type,
                extraction_method=data.extraction_method,
                deduplication_key=key,
                notes=data.notes,
                numeric_value=data.measurable_value,
                is_contradicted=False,
            )
        )
        self.repository.attach_source(signal.id, source.id, supporting_text, primary=source.is_primary_source, now=now)
        contradictions = self._find_contradictions(signal)
        if contradictions:
            signal.is_contradicted = True
            for other in contradictions:
                other.is_contradicted = True
                other.review_status = ReviewStatus.PENDING
        if self._can_auto_approve(signal, source):
            self.review_signal(
                signal.id,
                reviewer="context-engine",
                decision=ReviewStatus.APPROVED,
                reason="validated official high-confidence evidence",
                reviewed_at=now,
            )
        return signal, True

    def review_signal(
        self,
        signal_id: UUID,
        *,
        reviewer: str,
        decision: ReviewStatus,
        reason: str,
        reviewed_at: datetime | None = None,
    ) -> ContextSignal:
        if decision == ReviewStatus.PENDING:
            raise ValueError("pending is not a review decision")
        signal = self.repository.get_signal(signal_id)
        if signal is None:
            raise ValueError("context signal does not exist")
        previous = signal.review_status
        now = reviewed_at or utc_now()
        self.repository.append_review(
            ContextReview(
                context_signal_id=signal.id,
                reviewer=reviewer,
                decision=decision,
                reason=reason,
                reviewed_at=now,
                previous_status=previous,
                new_status=decision,
                created_at=now,
            )
        )
        signal.review_status = decision
        return signal

    def _can_auto_approve(self, signal: ContextSignal, source: ContextSource) -> bool:
        return (
            ExtractionMethod(signal.extraction_method) != ExtractionMethod.MANUAL
            and ContextLabel(signal.label) in AUTO_LABELS
            and ContextLabel(signal.label) not in {ContextLabel.CONFIRMED_INJURY, ContextLabel.RECENT_SURGERY}
            and ClaimType(signal.claim_type) in {ClaimType.CONFIRMED_FACT, ClaimType.DIRECT_STATEMENT}
            and signal.confidence >= Decimal(str(self.settings.context_min_auto_approval_confidence))
            and source.reliability_score >= Decimal(str(self.settings.context_min_auto_approval_source_reliability))
            and not signal.is_contradicted
        )

    def _find_contradictions(self, signal: ContextSignal) -> list[ContextSignal]:
        candidates = self.repository.signals_for_fighter(signal.fighter_id)
        return [
            item
            for item in candidates
            if item.id != signal.id
            and item.category == signal.category
            and item.fight_id == signal.fight_id
            and item.direction != signal.direction
            and abs((_utc(item.occurred_at) - _utc(signal.occurred_at)).days) <= 7
        ]


def build_signal_deduplication_key(data: ContextSignalInput) -> str:
    claim = re.sub(r"\s+", " ", (data.notes or "").strip().lower())
    raw = "|".join(
        (
            str(data.fighter_id),
            str(data.fight_id or ""),
            data.category,
            data.label,
            data.occurred_at.date().isoformat(),
            claim,
        )
    )
    return hashlib.sha256(raw.encode()).hexdigest()


def _utc(value: datetime) -> datetime:
    return value.astimezone(UTC) if value.tzinfo else value.replace(tzinfo=UTC)
