from datetime import date
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, aliased

from app.database.models.event import Event
from app.database.models.fight import Fight
from app.database.models.fighter import Fighter


class EventRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def upcoming(self, *, from_date: date, limit: int) -> list[tuple[Event, int]]:
        return list(
            self.session.execute(
                select(Event, func.count(Fight.id))
                .outerjoin(Fight, Fight.event_id == Event.id)
                .where(Event.event_date >= from_date)
                .group_by(Event.id)
                .order_by(Event.event_date, Event.name)
                .limit(limit)
            ).tuples()
        )

    def get(self, event_id: UUID) -> Event | None:
        return self.session.get(Event, event_id)

    def fight_card(self, event_id: UUID) -> list[tuple[Fight, Fighter, Fighter]]:
        fighter_a = aliased(Fighter)
        fighter_b = aliased(Fighter)
        return list(
            self.session.execute(
                select(Fight, fighter_a, fighter_b)
                .join(fighter_a, fighter_a.id == Fight.fighter_a_id)
                .join(fighter_b, fighter_b.id == Fight.fighter_b_id)
                .where(Fight.event_id == event_id)
                .order_by(Fight.id)
            ).tuples()
        )

    def fight(self, fight_id: UUID) -> tuple[Fight, Fighter, Fighter] | None:
        fighter_a = aliased(Fighter)
        fighter_b = aliased(Fighter)
        return (
            self.session.execute(
                select(Fight, fighter_a, fighter_b)
                .join(fighter_a, fighter_a.id == Fight.fighter_a_id)
                .join(fighter_b, fighter_b.id == Fight.fighter_b_id)
                .where(Fight.id == fight_id)
            )
            .tuples()
            .one_or_none()
        )
