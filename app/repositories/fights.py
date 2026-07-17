from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from uuid import UUID

from sqlalchemy import Select, or_, select
from sqlalchemy.orm import Session, aliased

from app.database.models.event import Event
from app.database.models.fight import Fight
from app.database.models.fighter import Fighter


class FighterOutcome(StrEnum):
    WIN = "win"
    LOSS = "loss"
    DRAW = "draw"
    NO_CONTEST = "no_contest"
    OVERTURNED = "overturned"


@dataclass(frozen=True, slots=True)
class FightFilters:
    weight_class: str | None = None
    scheduled_rounds: int | None = None
    opponent_stance: str | None = None
    outcomes: frozenset[FighterOutcome] | None = None


class FightRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def for_fighter(
        self,
        fighter_id: UUID,
        *,
        as_of: date,
        filters: FightFilters | None = None,
    ) -> list[tuple[Fight, date]]:
        filters = filters or FightFilters()
        statement = self._base_query(fighter_id, as_of)
        if filters.weight_class:
            statement = statement.where(Fight.weight_class == filters.weight_class)
        if filters.scheduled_rounds:
            statement = statement.where(Fight.scheduled_rounds == filters.scheduled_rounds)
        if filters.outcomes:
            outcome_conditions = []
            if FighterOutcome.WIN in filters.outcomes:
                outcome_conditions.append(Fight.winner_id == fighter_id)
            if FighterOutcome.LOSS in filters.outcomes:
                outcome_conditions.append(Fight.loser_id == fighter_id)
            result_outcomes = filters.outcomes & {
                FighterOutcome.DRAW,
                FighterOutcome.NO_CONTEST,
                FighterOutcome.OVERTURNED,
            }
            if result_outcomes:
                outcome_conditions.append(Fight.result.in_([outcome.value for outcome in result_outcomes]))
            statement = statement.where(or_(*outcome_conditions))
        if filters.opponent_stance:
            opponent = aliased(Fighter)
            statement = statement.join(
                opponent,
                or_(
                    (Fight.fighter_a_id == fighter_id) & (opponent.id == Fight.fighter_b_id),
                    (Fight.fighter_b_id == fighter_id) & (opponent.id == Fight.fighter_a_id),
                ),
            ).where(opponent.stance == filters.opponent_stance)
        return [(row[0], row[1]) for row in self.session.execute(statement)]

    @staticmethod
    def _base_query(fighter_id: UUID, as_of: date) -> Select[tuple[Fight, date]]:
        return (
            select(Fight, Event.event_date)
            .join(Event, Event.id == Fight.event_id)
            .where(or_(Fight.fighter_a_id == fighter_id, Fight.fighter_b_id == fighter_id))
            .where(Event.event_date <= as_of)
            .order_by(Event.event_date.desc(), Fight.id)
        )
