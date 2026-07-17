from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.context.enums import ReviewStatus
from app.database.models.context import (
    ContextAdjustment,
    ContextDocument,
    ContextFeatureValue,
    ContextReview,
    ContextSignal,
    ContextSignalSource,
    ContextSource,
)


class ContextRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def save_source(self, source: ContextSource) -> ContextSource:
        if source.url:
            existing = self.session.scalar(select(ContextSource).where(ContextSource.url == source.url))
            if existing is not None:
                return existing
        self.session.add(source)
        self.session.flush()
        return source

    def save_document(self, document: ContextDocument) -> ContextDocument:
        existing = self.session.scalar(
            select(ContextDocument).where(ContextDocument.content_hash == document.content_hash)
        )
        if existing is not None:
            return existing
        self.session.add(document)
        self.session.flush()
        return document

    def find_duplicate_signal(self, deduplication_key: str) -> ContextSignal | None:
        return self.session.scalar(select(ContextSignal).where(ContextSignal.deduplication_key == deduplication_key))

    def save_signal(self, signal: ContextSignal) -> ContextSignal:
        self.session.add(signal)
        self.session.flush()
        return signal

    def attach_source(
        self, signal_id: UUID, source_id: UUID, supporting_text: str, *, primary: bool, now: datetime
    ) -> bool:
        existing = self.session.scalar(
            select(ContextSignalSource).where(
                ContextSignalSource.context_signal_id == signal_id,
                ContextSignalSource.context_source_id == source_id,
            )
        )
        if existing is not None:
            return False
        self.session.add(
            ContextSignalSource(
                context_signal_id=signal_id,
                context_source_id=source_id,
                supporting_text=supporting_text,
                is_primary_support=primary,
                created_at=now,
            )
        )
        self.session.flush()
        return True

    def list_pending(self) -> list[ContextSignal]:
        return list(
            self.session.scalars(
                select(ContextSignal)
                .where(ContextSignal.review_status == ReviewStatus.PENDING)
                .order_by(ContextSignal.created_at)
            )
        )

    def pending_page(self, *, limit: int, offset: int) -> tuple[list[ContextSignal], int]:
        condition = ContextSignal.review_status == ReviewStatus.PENDING
        total = self.session.scalar(select(func.count()).select_from(ContextSignal).where(condition)) or 0
        rows = list(self.session.scalars(
            select(ContextSignal).where(condition)
            .order_by(ContextSignal.created_at, ContextSignal.id).limit(limit).offset(offset)
        ))
        return rows, total

    def pending_for_fight(self, fight_id: UUID) -> list[ContextSignal]:
        return list(self.session.scalars(
            select(ContextSignal).where(
                ContextSignal.fight_id == fight_id,
                ContextSignal.review_status == ReviewStatus.PENDING,
            ).order_by(ContextSignal.created_at)
        ))

    def latest_adjustment(self, fighter_id: UUID, fight_id: UUID) -> ContextAdjustment | None:
        return self.session.scalar(
            select(ContextAdjustment).where(
                ContextAdjustment.fighter_id == fighter_id,
                ContextAdjustment.fight_id == fight_id,
            ).order_by(ContextAdjustment.calculated_at.desc(), ContextAdjustment.created_at.desc()).limit(1)
        )

    def get_signal(self, signal_id: UUID) -> ContextSignal | None:
        return self.session.get(ContextSignal, signal_id)

    def append_review(self, review: ContextReview) -> None:
        self.session.add(review)
        self.session.flush()

    def status_as_of(self, signal: ContextSignal, as_of_time: datetime) -> ReviewStatus:
        review = self.session.scalar(
            select(ContextReview)
            .where(ContextReview.context_signal_id == signal.id, ContextReview.reviewed_at <= as_of_time)
            .order_by(ContextReview.reviewed_at.desc(), ContextReview.created_at.desc())
            .limit(1)
        )
        return ReviewStatus(review.new_status) if review else ReviewStatus.PENDING

    def signals_as_of(self, fighter_id: UUID, fight_id: UUID, as_of_time: datetime) -> list[ContextSignal]:
        return list(
            self.session.scalars(
                select(ContextSignal)
                .where(
                    ContextSignal.fighter_id == fighter_id,
                    (ContextSignal.fight_id == fight_id) | (ContextSignal.fight_id.is_(None)),
                    ContextSignal.occurred_at <= as_of_time,
                    ContextSignal.created_at <= as_of_time,
                )
                .order_by(ContextSignal.occurred_at)
            )
        )

    def signals_for_fighter(self, fighter_id: UUID) -> list[ContextSignal]:
        return list(self.session.scalars(select(ContextSignal).where(ContextSignal.fighter_id == fighter_id)))

    def sources_for_signal_as_of(
        self, signal_id: UUID, as_of_time: datetime
    ) -> list[tuple[ContextSignalSource, ContextSource]]:
        return list(
            self.session.execute(
                select(ContextSignalSource, ContextSource)
                .join(ContextSource, ContextSource.id == ContextSignalSource.context_source_id)
                .where(
                    ContextSignalSource.context_signal_id == signal_id,
                    ContextSignalSource.created_at <= as_of_time,
                    ContextSource.published_at <= as_of_time,
                    ContextSource.captured_at <= as_of_time,
                )
                .order_by(ContextSignalSource.is_primary_support.desc(), ContextSource.reliability_score.desc())
            ).tuples()
        )

    def save_feature(self, feature: ContextFeatureValue) -> ContextFeatureValue:
        existing = self.session.scalar(
            select(ContextFeatureValue).where(
                ContextFeatureValue.fighter_id == feature.fighter_id,
                ContextFeatureValue.fight_id == feature.fight_id,
                ContextFeatureValue.feature_name == feature.feature_name,
                ContextFeatureValue.context_version == feature.context_version,
            )
        )
        if existing is not None:
            return existing
        self.session.add(feature)
        self.session.flush()
        return feature

    def save_adjustment(self, adjustment: ContextAdjustment) -> ContextAdjustment:
        self.session.add(adjustment)
        self.session.flush()
        return adjustment


def utc_now() -> datetime:
    return datetime.now(UTC)
