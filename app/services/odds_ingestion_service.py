from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, aliased, sessionmaker

from app.config import Settings, get_settings
from app.database.models.event import Event
from app.database.models.fight import Fight
from app.database.models.fighter import Fighter
from app.odds.client import OddsApiClient
from app.odds.matching import MatchResult, match_provider_event, normalise_fighter_name
from app.odds.schemas import NormalisedOddsSnapshot, OddsIngestionSummary, ProviderEvent
from app.repositories.odds import OddsRepository


class OddsIngestionService:
    def __init__(
        self,
        client: OddsApiClient,
        session_factory: sessionmaker[Session],
        settings: Settings | None = None,
    ) -> None:
        self.client = client
        self.session_factory = session_factory
        self.settings = settings or get_settings()

    def ingest_upcoming_ufc_odds(self, *, dry_run: bool = False) -> OddsIngestionSummary:
        started = datetime.now(UTC)
        provider_result = self.client.get_upcoming_moneyline_odds()
        counters = {
            "provider_events_received": len(provider_result.events),
            "provider_events_matched": 0,
            "provider_events_unmatched": 0,
            "bookmaker_markets_processed": 0,
            "snapshots_inserted": 0,
            "duplicate_snapshots_skipped": 0,
            "invalid_records_skipped": provider_result.invalid_records,
        }
        with self.session_factory() as session:
            repository = OddsRepository(session)
            candidates = _load_candidates(session)
            for event in provider_result.events:
                matched = match_provider_event(
                    event, candidates, tolerance_hours=float(self.settings.odds_event_match_tolerance_hours)
                )
                if matched.status == "matched":
                    counters["provider_events_matched"] += 1
                else:
                    counters["provider_events_unmatched"] += 1
                if not dry_run:
                    repository.upsert_provider_event(
                        now=started,
                        provider="the_odds_api",
                        provider_event_id=event.provider_event_id,
                        sport_key=event.sport_key,
                        home_team=event.home_team,
                        away_team=event.away_team,
                        commence_time=event.commence_time,
                        internal_event_id=matched.internal_event_id,
                        internal_fight_id=matched.internal_fight_id,
                        match_status=matched.status,
                    )
                for snapshot in normalise_event(event, matched, started):
                    counters["bookmaker_markets_processed"] += 1
                    if dry_run:
                        continue
                    if repository.insert_snapshot_if_new(snapshot):
                        counters["snapshots_inserted"] += 1
                    else:
                        counters["duplicate_snapshots_skipped"] += 1
            if dry_run:
                session.rollback()
            else:
                session.commit()
        quota = provider_result.quota
        return OddsIngestionSummary(
            **counters,
            requests_remaining=quota.requests_remaining,
            requests_used=quota.requests_used,
            last_request_cost=quota.last_request_cost,
            started_at=started,
            completed_at=datetime.now(UTC),
        )


def _load_candidates(session: Session) -> list[tuple[Fight, Event, Fighter, Fighter]]:
    fighter_a = aliased(Fighter)
    fighter_b = aliased(Fighter)
    return list(session.execute(
        select(Fight, Event, fighter_a, fighter_b)
        .join(Event, Event.id == Fight.event_id)
        .join(fighter_a, fighter_a.id == Fight.fighter_a_id)
        .join(fighter_b, fighter_b.id == Fight.fighter_b_id)
    ).tuples())


def normalise_event(
    event: ProviderEvent, matched: MatchResult, captured_at: datetime
) -> list[NormalisedOddsSnapshot]:
    selection_ids = {
        normalise_fighter_name(name): fighter_id for name, fighter_id in (matched.selections or {}).items()
    }
    snapshots = []
    for bookmaker in event.bookmakers:
        for market in bookmaker.markets:
            if market.key != "h2h":
                continue
            for outcome in market.outcomes:
                fighter_id = selection_ids.get(normalise_fighter_name(outcome.name))
                if matched.status == "matched" and fighter_id is None:
                    continue
                snapshots.append(NormalisedOddsSnapshot(
                    provider_event_id=event.provider_event_id,
                    internal_event_id=matched.internal_event_id,
                    internal_fight_id=matched.internal_fight_id,
                    internal_fighter_id=fighter_id,
                    sport_key=event.sport_key,
                    commence_time=event.commence_time,
                    bookmaker_key=bookmaker.key,
                    bookmaker_name=bookmaker.title,
                    selection_name=outcome.name,
                    decimal_odds=outcome.price,
                    implied_probability=(Decimal(1) / outcome.price).quantize(Decimal("0.00000001")),
                    bookmaker_last_update=market.last_update,
                    captured_at=captured_at,
                ))
    return snapshots
