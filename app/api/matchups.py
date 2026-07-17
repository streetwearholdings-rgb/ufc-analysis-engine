from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.dependencies import DatabaseSession
from app.repositories.fighters import FighterRepository
from app.repositories.matchups import MatchupRepository
from app.repositories.ratings import RatingRepository
from app.repositories.styles import StyleRepository
from app.schemas.matchup import MatchupResponse
from app.services.matchup_service import MatchupService

router = APIRouter(prefix="/api/v1/matchups", tags=["matchups"])


@router.get("/{fighter_a_id}/{fighter_b_id}", response_model=MatchupResponse)
def matchup(fighter_a_id: UUID, fighter_b_id: UUID, db: DatabaseSession) -> MatchupResponse:
    if fighter_a_id == fighter_b_id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Fighters must be different")
    fighters = FighterRepository(db)
    fighter_a = fighters.get(fighter_a_id)
    fighter_b = fighters.get(fighter_b_id)
    if fighter_a is None or fighter_b is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fighter not found")
    styles = StyleRepository(db)
    style_a = styles.latest_for_fighter(fighter_a_id)
    style_b = styles.latest_for_fighter(fighter_b_id)
    if style_a is None or style_b is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Style profile not found")
    if style_a.weight_class != style_b.weight_class:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="No common weight-class profile")
    ratings = RatingRepository(db)
    rating_a = ratings.latest_for_fighter(fighter_a_id, style_a.weight_class)
    rating_b = ratings.latest_for_fighter(fighter_b_id, style_b.weight_class)
    if rating_a is None or rating_b is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rating profile not found")
    response, _ = MatchupService(MatchupRepository(db)).compare(
        fighter_a, rating_a, style_a, fighter_b, rating_b, style_b
    )
    return response
