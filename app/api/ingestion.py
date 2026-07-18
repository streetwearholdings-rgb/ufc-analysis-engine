from fastapi import APIRouter, HTTPException, status

from app.database.session import SessionLocal
from app.dependencies import CalculationAccess, DatabaseSession
from app.ingestion.schemas import IngestionStatusResponse, UpcomingIngestionSummary
from app.ingestion.service import IngestionAlreadyRunningError, UpcomingIngestionService, ingestion_status
from app.odds.client import OddsApiClient
from app.odds.exceptions import OddsProviderError

router = APIRouter(prefix="/api/v1/admin", tags=["administration"])


@router.post("/ingest/upcoming", response_model=UpcomingIngestionSummary)
def ingest_upcoming(_: CalculationAccess) -> UpcomingIngestionSummary:
    try:
        return UpcomingIngestionService(OddsApiClient(), SessionLocal).ingest()
    except IngestionAlreadyRunningError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except OddsProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The configured UFC data provider could not complete ingestion.",
        ) from exc


@router.get("/ingestion/status", response_model=IngestionStatusResponse)
def get_ingestion_status(db: DatabaseSession, _: CalculationAccess) -> IngestionStatusResponse:
    return ingestion_status(db)
