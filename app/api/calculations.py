from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.dependencies import CalculationAccess, DatabaseSession
from app.schemas.calculations import CalculationResponse, RebuildResponse
from app.services.recalculation_service import RecalculationService

router = APIRouter(prefix="/api/v1/calculations", tags=["calculations"])


@router.post("/fighters/{fighter_id}", response_model=CalculationResponse)
def recalculate_fighter(fighter_id: UUID, db: DatabaseSession, _: CalculationAccess) -> CalculationResponse:
    try:
        windows = RecalculationService(db).recalculate_fighter(fighter_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return CalculationResponse(fighter_id=fighter_id, windows_rebuilt=windows)


@router.post("/rebuild", response_model=RebuildResponse)
def rebuild(db: DatabaseSession, _: CalculationAccess) -> RebuildResponse:
    processed, failed = RecalculationService(db).rebuild_all()
    return RebuildResponse(fighters_processed=processed, fighters_failed=failed)
