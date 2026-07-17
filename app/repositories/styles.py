from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models.fighter_style_score import FighterStyleScore


class StyleRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def latest_for_fighter(self, fighter_id: UUID) -> FighterStyleScore | None:
        statement = (
            select(FighterStyleScore)
            .where(FighterStyleScore.fighter_id == fighter_id)
            .order_by(FighterStyleScore.calculation_date.desc(), FighterStyleScore.created_at.desc())
            .limit(1)
        )
        return self.session.scalar(statement)

    def add(self, profile: FighterStyleScore) -> FighterStyleScore:
        self.session.add(profile)
        self.session.flush()
        return profile
