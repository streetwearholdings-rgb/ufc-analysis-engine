from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models.fighter_rating import FighterRating


class RatingRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def for_fighter(self, fighter_id: UUID) -> list[FighterRating]:
        statement = (
            select(FighterRating)
            .where(FighterRating.fighter_id == fighter_id)
            .order_by(FighterRating.rating_date.desc(), FighterRating.created_at.desc())
        )
        return list(self.session.scalars(statement))

    def add_all(self, ratings: list[FighterRating]) -> None:
        self.session.add_all(ratings)
        self.session.flush()

    def latest_for_fighter(self, fighter_id: UUID, weight_class: str | None = None) -> FighterRating | None:
        statement = select(FighterRating).where(FighterRating.fighter_id == fighter_id)
        if weight_class is not None:
            statement = statement.where(FighterRating.weight_class == weight_class)
        statement = statement.order_by(FighterRating.rating_date.desc(), FighterRating.created_at.desc()).limit(1)
        return self.session.scalar(statement)
