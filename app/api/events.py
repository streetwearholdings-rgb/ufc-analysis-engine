from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from app.dependencies import DatabaseSession
from app.schemas.events import ConsolidatedFightAnalysis, EventFightCard, EventSummary
from app.services.fight_analysis_service import FightAnalysisNotReadyError, FightAnalysisService

router = APIRouter(prefix="/api/v1", tags=["events and analysis"])


@router.get(
    "/events/upcoming",
    response_model=list[EventSummary],
    summary="List upcoming UFC events",
    description="Returns events on or after `from_date`, ordered chronologically.",
)
def upcoming_events(
    db: DatabaseSession,
    from_date: Annotated[date | None, Query()] = None,
    limit: int = Query(default=25, ge=1, le=100),
) -> list[EventSummary]:
    return FightAnalysisService(db).upcoming_events(from_date=from_date or date.today(), limit=limit)


@router.get(
    "/events/{event_id}/fights",
    response_model=EventFightCard,
    summary="Get an event fight card",
)
def event_fight_card(event_id: UUID, db: DatabaseSession) -> EventFightCard:
    try:
        return FightAnalysisService(db).event_fight_card(event_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get(
    "/fights/{fight_id}/analysis",
    response_model=ConsolidatedFightAnalysis,
    summary="Get consolidated fight analysis",
    description="Combines the latest persisted model/context prediction with current matched moneyline odds.",
)
def consolidated_fight_analysis(fight_id: UUID, db: DatabaseSession) -> ConsolidatedFightAnalysis:
    try:
        return FightAnalysisService(db).consolidated(fight_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except FightAnalysisNotReadyError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
