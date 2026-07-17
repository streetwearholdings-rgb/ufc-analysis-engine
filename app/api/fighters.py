from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.database.models.fighter import Fighter
from app.database.models.fighter_rating import FighterRating
from app.database.models.fighter_rolling_stat import FighterRollingStat
from app.dependencies import DatabaseSession
from app.repositories.fighters import FighterRepository
from app.repositories.performances import PerformanceRepository
from app.repositories.ratings import RatingRepository
from app.repositories.stats import StatsRepository
from app.repositories.styles import StyleRepository
from app.schemas.fighter import FighterResponse
from app.schemas.performance import FightPerformanceResponse
from app.schemas.ratings import FighterRatingResponse
from app.schemas.rolling_stats import RollingStatResponse
from app.schemas.style import FighterStyleResponse
from app.services.performance_service import PerformanceService
from app.services.style_service import stored_style_response

router = APIRouter(prefix="/api/v1/fighters", tags=["fighters"])


@router.get("/{fighter_id}", response_model=FighterResponse)
def fighter_profile(fighter_id: UUID, db: DatabaseSession) -> Fighter:
    fighter = FighterRepository(db).get(fighter_id)
    if fighter is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fighter not found")
    return fighter


@router.get("/{fighter_id}/rolling-stats", response_model=list[RollingStatResponse])
def fighter_rolling_stats(fighter_id: UUID, db: DatabaseSession) -> list[FighterRollingStat]:
    if FighterRepository(db).get(fighter_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fighter not found")
    return StatsRepository(db).rolling_for_fighter(fighter_id)


@router.get("/{fighter_id}/performances", response_model=list[FightPerformanceResponse])
def fighter_performances(fighter_id: UUID, db: DatabaseSession) -> list[FightPerformanceResponse]:
    if FighterRepository(db).get(fighter_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fighter not found")
    return PerformanceService(PerformanceRepository(db)).for_fighter(fighter_id)


@router.get("/{fighter_id}/ratings", response_model=list[FighterRatingResponse])
def fighter_ratings(fighter_id: UUID, db: DatabaseSession) -> list[FighterRating]:
    if FighterRepository(db).get(fighter_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fighter not found")
    return RatingRepository(db).for_fighter(fighter_id)


@router.get("/{fighter_id}/style", response_model=FighterStyleResponse)
def fighter_style(fighter_id: UUID, db: DatabaseSession) -> FighterStyleResponse:
    if FighterRepository(db).get(fighter_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fighter not found")
    profile = StyleRepository(db).latest_for_fighter(fighter_id)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Style profile not found")
    return stored_style_response(profile)
