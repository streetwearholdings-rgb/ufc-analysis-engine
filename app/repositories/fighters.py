from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models.fighter import Fighter


class FighterRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, fighter_id: UUID) -> Fighter | None:
        return self.session.get(Fighter, fighter_id)

    def get_by_external_id(self, external_id: str) -> Fighter | None:
        return self.session.query(Fighter).filter(Fighter.external_id == external_id).one_or_none()

    def active(self) -> list[Fighter]:
        return list(self.session.scalars(select(Fighter).where(Fighter.active.is_(True)).order_by(Fighter.id)))
