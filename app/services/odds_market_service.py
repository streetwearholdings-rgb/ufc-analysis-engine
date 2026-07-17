from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database.models.fighter import Fighter
from app.odds.schemas import FightMarketOdds, MarketSelectionOdds
from app.repositories.odds import OddsRepository


class OddsMarketService:
    def __init__(self, session: Session, settings: Settings | None = None) -> None:
        self.session = session
        self.settings = settings or get_settings()
        self.repository = OddsRepository(session)

    def get_fight_market_odds(self, fight_id: UUID, *, exclude_stale: bool = True) -> FightMarketOdds:
        now = datetime.now(UTC)
        cutoff = now - timedelta(minutes=self.settings.odds_api_stale_after_minutes) if exclude_stale else None
        latest = self.repository.get_latest_moneyline_odds_for_fight(fight_id, updated_after=cutoff)
        best = self.repository.get_best_moneyline_odds_for_fight(fight_id, updated_after=cutoff)
        counts: dict[UUID, int] = {}
        for row in latest:
            if row.internal_fighter_id is not None:
                counts[row.internal_fighter_id] = counts.get(row.internal_fighter_id, 0) + 1
        fighters = {
            fighter.id: fighter
            for fighter in self.session.scalars(select(Fighter).where(Fighter.id.in_(counts)))
        } if counts else {}
        selections = []
        for row in best:
            fighter_id = row.internal_fighter_id
            if fighter_id is None or fighter_id not in fighters:
                continue
            fighter = fighters[fighter_id]
            update = row.bookmaker_last_update
            if update.tzinfo is None:
                update = update.replace(tzinfo=UTC)
            selections.append(MarketSelectionOdds(
                fighter_id=fighter_id,
                fighter_name=f"{fighter.first_name} {fighter.last_name}".strip(),
                best_decimal_odds=row.decimal_odds,
                best_bookmaker=row.bookmaker_name,
                raw_implied_probability=row.implied_probability,
                bookmaker_last_update=update,
                age_seconds=max(0, int((now - update).total_seconds())),
                bookmaker_count=counts[fighter_id],
            ))
        return FightMarketOdds(fight_id=fight_id, selections=selections)
