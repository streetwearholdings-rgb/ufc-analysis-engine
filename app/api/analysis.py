import logging
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import JSONResponse

from app.analysis.read_service import AnalysisReadService
from app.analysis.schemas import (
    AnalysisFilters,
    AnalysisPage,
    AnalysisResponse,
    AnalysisRunRequest,
    AnalysisRunSummary,
    AnalysisStatusResponse,
    ModelStatusResponse,
)
from app.analysis.service import (
    AnalysisAlreadyRunningError,
    UpcomingAnalysisService,
    analysis_status,
    model_status,
)
from app.database.session import SessionLocal
from app.dependencies import CalculationAccess, DatabaseSession

router = APIRouter(tags=["fight analysis"])
logger = logging.getLogger(__name__)


@router.post(
    "/api/v1/admin/analysis/run-upcoming",
    response_model=AnalysisRunSummary,
    responses={
        409: {"description": "An analysis run is already active"},
        500: {"description": "Safe failure response"},
    },
)
def run_upcoming_analysis(body: AnalysisRunRequest, _: CalculationAccess) -> AnalysisRunSummary | JSONResponse:
    try:
        return UpcomingAnalysisService(SessionLocal).run(event_id=body.event_id, force=body.force)
    except AnalysisAlreadyRunningError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("analysis_api_failed error_type=%s", type(exc).__name__)
        return JSONResponse(
            status_code=500,
            content={"error": "analysis_failed", "message": "The fight analysis could not be completed."},
        )


@router.get("/api/v1/admin/analysis/status", response_model=AnalysisStatusResponse)
def get_analysis_status(db: DatabaseSession, _: CalculationAccess) -> AnalysisStatusResponse:
    return analysis_status(db)


@router.get("/api/v1/analysis/upcoming", response_model=AnalysisPage)
def upcoming_analysis(
    db: DatabaseSession,
    event_id: UUID | None = None,
    minimum_confidence: Annotated[Decimal | None, Query(ge=0, le=1)] = None,
    minimum_value_edge: Decimal | None = None,
    recommendation_status: str | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> AnalysisPage:
    return AnalysisReadService(db).page(
        AnalysisFilters(
            event_id=event_id,
            minimum_confidence=minimum_confidence,
            minimum_value_edge=minimum_value_edge,
            recommendation_status=recommendation_status,
            limit=limit,
            offset=offset,
        )
    )


@router.get("/api/v1/analysis/fights/{fight_id}", response_model=AnalysisResponse)
def fight_analysis(fight_id: UUID, db: DatabaseSession) -> AnalysisResponse:
    try:
        return AnalysisReadService(db).fight(fight_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/api/v1/picks/upcoming", response_model=AnalysisPage)
def upcoming_picks(
    db: DatabaseSession,
    event_id: UUID | None = None,
    market: str | None = None,
    confidence_tier: str | None = None,
    minimum_expected_value: Decimal | None = None,
    include_no_bets: bool = False,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> AnalysisPage:
    return AnalysisReadService(db).picks(
        event_id=event_id,
        market=market,
        confidence_tier=confidence_tier,
        minimum_expected_value=minimum_expected_value,
        include_no_bets=include_no_bets,
        limit=limit,
        offset=offset,
    )


@router.get("/api/v1/model/status", response_model=ModelStatusResponse)
def get_model_status(db: DatabaseSession) -> ModelStatusResponse:
    return model_status(db)
