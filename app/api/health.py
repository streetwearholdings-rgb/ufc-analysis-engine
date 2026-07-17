import logging
from typing import Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.dependencies import DatabaseSession

router = APIRouter(tags=["health"])
logger = logging.getLogger(__name__)


class HealthResponse(BaseModel):
    status: Literal["ok"]
    database: Literal["ok"]


@router.get("/health", response_model=HealthResponse)
def health(db: DatabaseSession) -> HealthResponse:
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        logger.exception("health_check_database_unavailable")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable",
        ) from exc
    return HealthResponse(status="ok", database="ok")
