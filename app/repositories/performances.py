from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models.fight_performance_score import FightPerformanceScore


class PerformanceRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def for_fighter(self, fighter_id: UUID) -> list[FightPerformanceScore]:
        statement = (
            select(FightPerformanceScore)
            .where(FightPerformanceScore.fighter_id == fighter_id)
            .order_by(FightPerformanceScore.calculated_at.desc(), FightPerformanceScore.fight_id)
        )
        return list(self.session.scalars(statement))

    def add(self, score: FightPerformanceScore) -> FightPerformanceScore:
        self.session.add(score)
        self.session.flush()
        return score
