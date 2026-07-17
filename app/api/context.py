from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from app.context.enums import ReviewStatus
from app.dependencies import CalculationAccess, DatabaseSession
from app.schemas.events import PendingContextPage, ReviewRequest, ReviewResponse
from app.services.context_service import ContextService
from app.services.fight_analysis_service import FightAnalysisService

router = APIRouter(prefix="/api/v1/context", tags=["context"])
admin_router = APIRouter(prefix="/api/v1/admin/context", tags=["context administration"])


@router.get(
    "/reviews/pending",
    response_model=PendingContextPage,
    summary="List pending context reviews",
)
def pending_context_reviews(
    db: DatabaseSession,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> PendingContextPage:
    return FightAnalysisService(db).pending_context(limit=limit, offset=offset)


@admin_router.post(
    "/signals/{signal_id}/approve",
    response_model=ReviewResponse,
    summary="Approve a context signal",
)
def approve_context_signal(
    signal_id: UUID, payload: ReviewRequest, db: DatabaseSession, _: CalculationAccess
) -> ReviewResponse:
    return _review(signal_id, payload, db, ReviewStatus.APPROVED)


@admin_router.post(
    "/signals/{signal_id}/reject",
    response_model=ReviewResponse,
    summary="Reject a context signal",
)
def reject_context_signal(
    signal_id: UUID, payload: ReviewRequest, db: DatabaseSession, _: CalculationAccess
) -> ReviewResponse:
    return _review(signal_id, payload, db, ReviewStatus.REJECTED)


def _review(signal_id: UUID, payload: ReviewRequest, db: DatabaseSession, decision: ReviewStatus) -> ReviewResponse:
    reviewed_at = datetime.now(UTC)
    try:
        signal = ContextService(db).review_signal(
            signal_id,
            reviewer=payload.reviewer,
            decision=decision,
            reason=payload.reason,
            reviewed_at=reviewed_at,
        )
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return ReviewResponse(signal_id=signal.id, review_status=signal.review_status, reviewed_at=reviewed_at)
