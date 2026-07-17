from collections import defaultdict
from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.calculations.rolling_averages import FightStatLine, build_fight_stat_line
from app.database.models.fight_round_stat import FightRoundStat
from app.database.models.fighter_rolling_stat import FighterRollingStat
from app.repositories.fights import FightFilters, FightRepository


class StatsRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def by_fights(self, fight_ids: list[UUID]) -> dict[UUID, list[FightRoundStat]]:
        if not fight_ids:
            return {}
        rows = self.session.scalars(
            select(FightRoundStat)
            .where(FightRoundStat.fight_id.in_(fight_ids))
            .order_by(FightRoundStat.fight_id, FightRoundStat.round_number, FightRoundStat.fighter_id)
        )
        grouped: dict[UUID, list[FightRoundStat]] = defaultdict(list)
        for row in rows:
            grouped[row.fight_id].append(row)
        return dict(grouped)

    def fight_stat_lines(
        self,
        fighter_id: UUID,
        *,
        as_of: date,
        filters: FightFilters | None = None,
    ) -> list[FightStatLine]:
        fights = FightRepository(self.session).for_fighter(fighter_id, as_of=as_of, filters=filters)
        rows_by_fight = self.by_fights([fight.id for fight, _ in fights])
        return [
            build_fight_stat_line(fighter_id, fight, event_date, rows_by_fight.get(fight.id, []))
            for fight, event_date in fights
        ]

    def rolling_for_fighter(self, fighter_id: UUID) -> list[FighterRollingStat]:
        return list(
            self.session.scalars(
                select(FighterRollingStat)
                .where(FighterRollingStat.fighter_id == fighter_id)
                .order_by(FighterRollingStat.calculation_date.desc(), FighterRollingStat.window_type)
            )
        )

    def replace_rolling(self, row: FighterRollingStat) -> FighterRollingStat:
        existing = self.session.scalar(
            select(FighterRollingStat).where(
                FighterRollingStat.fighter_id == row.fighter_id,
                FighterRollingStat.calculation_date == row.calculation_date,
                FighterRollingStat.window_type == row.window_type,
                FighterRollingStat.weight_class == row.weight_class,
            )
        )
        if existing is None:
            self.session.add(row)
            return row
        for column in FighterRollingStat.__table__.columns:
            if column.name not in {"id", "fighter_id", "calculation_date", "window_type", "weight_class", "created_at"}:
                setattr(existing, column.name, getattr(row, column.name))
        return existing
