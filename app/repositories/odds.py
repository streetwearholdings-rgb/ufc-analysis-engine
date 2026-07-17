from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models.odds_provider_event import OddsProviderEvent
from app.database.models.odds_snapshot import OddsSnapshot
from app.odds.schemas import NormalisedOddsSnapshot


class OddsRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def upsert_provider_event(self, *, now: datetime, **values: object) -> OddsProviderEvent:
        row = self.session.scalar(
            select(OddsProviderEvent).where(
                OddsProviderEvent.provider == values["provider"],
                OddsProviderEvent.provider_event_id == values["provider_event_id"],
            )
        )
        if row is None:
            row = OddsProviderEvent(first_seen_at=now, last_seen_at=now, **values)
            self.session.add(row)
        else:
            for name, value in values.items():
                setattr(row, name, value)
            row.last_seen_at = now
        self.session.flush()
        return row

    def insert_snapshot_if_new(self, snapshot: NormalisedOddsSnapshot) -> bool:
        values = snapshot.model_dump(exclude={"sport_key", "commence_time"})
        duplicate = self.session.scalar(
            select(OddsSnapshot.id).where(
                OddsSnapshot.provider == snapshot.provider,
                OddsSnapshot.provider_event_id == snapshot.provider_event_id,
                OddsSnapshot.bookmaker_key == snapshot.bookmaker_key,
                OddsSnapshot.market_type == snapshot.market_type,
                OddsSnapshot.selection_name == snapshot.selection_name,
                OddsSnapshot.decimal_odds == snapshot.decimal_odds,
                OddsSnapshot.bookmaker_last_update == snapshot.bookmaker_last_update,
            )
        )
        if duplicate is not None:
            return False
        self.session.add(OddsSnapshot(**values))
        self.session.flush()
        return True

    def get_odds_history_for_fight(self, fight_id: UUID) -> list[OddsSnapshot]:
        return list(
            self.session.scalars(
                select(OddsSnapshot)
                .where(OddsSnapshot.internal_fight_id == fight_id, OddsSnapshot.internal_fighter_id.is_not(None))
                .order_by(OddsSnapshot.bookmaker_last_update.desc(), OddsSnapshot.captured_at.desc())
            )
        )

    def get_latest_moneyline_odds_for_fight(
        self, fight_id: UUID, *, updated_after: datetime | None = None
    ) -> list[OddsSnapshot]:
        rows = self.get_odds_history_for_fight(fight_id)
        latest: dict[tuple[UUID, str], OddsSnapshot] = {}
        for row in rows:
            if row.market_type != "moneyline" or row.internal_fighter_id is None:
                continue
            if updated_after is not None and _aware(row.bookmaker_last_update) < updated_after:
                continue
            key = (row.internal_fighter_id, row.bookmaker_key)
            if key not in latest:
                latest[key] = row
        return list(latest.values())

    def get_best_moneyline_odds_for_fight(
        self, fight_id: UUID, *, updated_after: datetime | None = None
    ) -> list[OddsSnapshot]:
        best: dict[UUID, OddsSnapshot] = {}
        for row in self.get_latest_moneyline_odds_for_fight(fight_id, updated_after=updated_after):
            fighter_id = row.internal_fighter_id
            if fighter_id is not None and (fighter_id not in best or row.decimal_odds > best[fighter_id].decimal_odds):
                best[fighter_id] = row
        return list(best.values())


def _aware(value: datetime) -> datetime:
    return value.astimezone(UTC) if value.tzinfo is not None else value.replace(tzinfo=UTC)
