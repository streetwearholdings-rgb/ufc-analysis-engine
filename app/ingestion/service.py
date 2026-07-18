import hashlib
import logging
import threading
from datetime import UTC, date, datetime

from sqlalchemy import select, text
from sqlalchemy.orm import Session, sessionmaker

from app.database.models.event import Event
from app.database.models.fight import Fight
from app.database.models.fighter import Fighter
from app.database.models.ingestion_run import IngestionRun
from app.ingestion.schemas import IngestionStatusResponse, UpcomingIngestionSummary
from app.odds.client import OddsApiClient
from app.odds.matching import MatchResult, normalise_fighter_name
from app.odds.schemas import ProviderEvent
from app.repositories.odds import OddsRepository
from app.services.odds_ingestion_service import normalise_event

logger = logging.getLogger(__name__)
PROVIDER = "the_odds_api"
LOCK_KEY = 8_624_236_627
_process_lock = threading.Lock()


class IngestionAlreadyRunningError(RuntimeError):
    pass


class UpcomingIngestionService:
    def __init__(self, client: OddsApiClient, session_factory: sessionmaker[Session]) -> None:
        self.client = client
        self.session_factory = session_factory

    def ingest(self) -> UpcomingIngestionSummary:
        started = datetime.now(UTC)
        with self.session_factory() as session:
            process_locked = False
            try:
                process_locked = _acquire_lock(session)
                if not process_locked:
                    raise IngestionAlreadyRunningError("An upcoming ingestion is already running")
                run = IngestionRun(provider=PROVIDER, status="running", started_at=started, records={})
                session.add(run)
                session.commit()

                result = self.client.get_upcoming_moneyline_odds()
                provider_events = [
                    item for item in result.events if _utc_date(item.commence_time) >= datetime.now(UTC).date()
                ]
                counts = self._persist(session, provider_events, started)
                completed = datetime.now(UTC)
                run.status = "success"
                run.completed_at = completed
                run.events_processed = counts["events_processed"]
                run.fights_processed = counts["fights_processed"]
                run.fighters_processed = counts["fighters_processed"]
                run.odds_processed = counts["odds_processed"]
                run.records = counts
                session.commit()
                logger.info(
                    "upcoming_ingestion_succeeded events=%s fights=%s fighters=%s odds=%s",
                    counts["events_processed"],
                    counts["fights_processed"],
                    counts["fighters_processed"],
                    counts["odds_processed"],
                )
                return UpcomingIngestionSummary(
                    **{key: counts[key] for key in _SUMMARY_KEYS},
                    records=counts,
                    started_at=started,
                    completed_at=completed,
                )
            except IngestionAlreadyRunningError:
                raise
            except Exception as exc:
                session.rollback()
                completed = datetime.now(UTC)
                persisted_run = session.scalar(
                    select(IngestionRun).where(IngestionRun.started_at == started, IngestionRun.provider == PROVIDER)
                )
                if persisted_run is not None:
                    persisted_run.status = "failed"
                    persisted_run.completed_at = completed
                    persisted_run.error_summary = _safe_error(exc)
                    session.commit()
                logger.error("upcoming_ingestion_failed error_type=%s", type(exc).__name__)
                raise
            finally:
                if process_locked:
                    _release_lock(session)

    def _persist(self, session: Session, provider_events: list[ProviderEvent], now: datetime) -> dict[str, int]:
        odds_repository = OddsRepository(session)
        event_ids: set[object] = set()
        fighter_ids: set[object] = set()
        fights = 0
        odds = 0
        created_events = created_fighters = created_fights = inserted_odds = duplicate_odds = 0

        for provider_event in provider_events:
            event, created = _upsert_event(session, provider_event)
            created_events += int(created)
            event_ids.add(event.id)
            fighter_a, a_created = _upsert_fighter(session, provider_event.home_team)
            fighter_b, b_created = _upsert_fighter(session, provider_event.away_team)
            created_fighters += int(a_created) + int(b_created)
            fighter_ids.update((fighter_a.id, fighter_b.id))
            fight, fight_created = _upsert_fight(session, provider_event, event, fighter_a, fighter_b)
            created_fights += int(fight_created)
            fights += 1
            match = MatchResult(
                "matched",
                event.id,
                fight.id,
                {provider_event.home_team: fighter_a.id, provider_event.away_team: fighter_b.id},
            )
            odds_repository.upsert_provider_event(
                now=now,
                provider=PROVIDER,
                provider_event_id=provider_event.provider_event_id,
                sport_key=provider_event.sport_key,
                home_team=provider_event.home_team,
                away_team=provider_event.away_team,
                commence_time=provider_event.commence_time.astimezone(UTC),
                internal_event_id=event.id,
                internal_fight_id=fight.id,
                match_status="matched",
            )
            for snapshot in normalise_event(provider_event, match, now):
                odds += 1
                if odds_repository.insert_snapshot_if_new(snapshot):
                    inserted_odds += 1
                else:
                    duplicate_odds += 1
        session.flush()
        return {
            "events_processed": len(event_ids),
            "fights_processed": fights,
            "fighters_processed": len(fighter_ids),
            "odds_processed": odds,
            "events_created": created_events,
            "fights_created": created_fights,
            "fighters_created": created_fighters,
            "odds_inserted": inserted_odds,
            "duplicate_odds_skipped": duplicate_odds,
        }


def ingestion_status(session: Session) -> IngestionStatusResponse:
    rows = list(
        session.scalars(
            select(IngestionRun)
            .where(IngestionRun.provider == PROVIDER)
            .order_by(IngestionRun.started_at.desc())
        )
    )
    success = next((row for row in rows if row.status == "success"), None)
    failure = next((row for row in rows if row.status == "failed"), None)
    return IngestionStatusResponse(
        running=any(row.status == "running" for row in rows),
        last_successful_ingestion_time=success.completed_at if success else None,
        last_failure_time=failure.completed_at if failure else None,
        records_processed=success.records if success else {},
        safe_error_summary=failure.error_summary if failure else None,
    )


def _upsert_event(session: Session, item: ProviderEvent) -> tuple[Event, bool]:
    event_date = _utc_date(item.commence_time)
    external_id = f"{PROVIDER}:card:{item.sport_key}:{event_date.isoformat()}"
    event = session.scalar(select(Event).where(Event.external_id == external_id))
    created = event is None
    if event is None:
        event = Event(
            external_id=external_id,
            name=f"{item.sport_title} card — {event_date.isoformat()}",
            location=None,
        )
        session.add(event)
    event.event_date = event_date
    event.promotion = "UFC"
    session.flush()
    return event, created


def _upsert_fighter(session: Session, provider_name: str) -> tuple[Fighter, bool]:
    normalised = normalise_fighter_name(provider_name)
    digest = hashlib.sha256(normalised.encode()).hexdigest()[:24]
    external_id = f"{PROVIDER}:fighter:{digest}"
    fighter = session.scalar(select(Fighter).where(Fighter.external_id == external_id))
    created = fighter is None
    first_name, last_name = _split_name(provider_name)
    if fighter is None:
        fighter = Fighter(external_id=external_id, first_name=first_name, last_name=last_name)
        session.add(fighter)
    else:
        fighter.first_name = first_name
        fighter.last_name = last_name
    fighter.active = True
    session.flush()
    return fighter, created


def _upsert_fight(
    session: Session, item: ProviderEvent, event: Event, fighter_a: Fighter, fighter_b: Fighter
) -> tuple[Fight, bool]:
    external_id = f"{PROVIDER}:fight:{item.provider_event_id}"
    fight = session.scalar(select(Fight).where(Fight.external_id == external_id))
    created = fight is None
    if fight is None:
        fight = Fight(
            external_id=external_id,
            winner_id=None,
            loser_id=None,
            weight_class=None,
            scheduled_rounds=None,
            completed_rounds=0,
            result="scheduled",
        )
        session.add(fight)
    fight.event_id = event.id
    fight.fighter_a_id = fighter_a.id
    fight.fighter_b_id = fighter_b.id
    session.flush()
    return fight, created


def _split_name(value: str) -> tuple[str, str]:
    parts = value.strip().split(maxsplit=1)
    return (parts[0], parts[1]) if len(parts) == 2 else ("", parts[0])


def _utc_date(value: datetime) -> date:
    return value.astimezone(UTC).date()


def _safe_error(exc: Exception) -> str:
    return {
        "OddsProviderAuthenticationError": "Provider authentication failed.",
        "OddsProviderRateLimitError": "Provider rate limit exceeded.",
        "OddsProviderConfigurationError": "Provider configuration is incomplete.",
    }.get(type(exc).__name__, "Ingestion failed; review server logs.")


def _acquire_lock(session: Session) -> bool:
    if session.bind is not None and session.bind.dialect.name == "postgresql":
        return bool(session.scalar(text("SELECT pg_try_advisory_lock(:key)"), {"key": LOCK_KEY}))
    return _process_lock.acquire(blocking=False)


def _release_lock(session: Session) -> None:
    if session.bind is not None and session.bind.dialect.name == "postgresql":
        session.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": LOCK_KEY})
    elif _process_lock.locked():
        _process_lock.release()


_SUMMARY_KEYS = ("events_processed", "fights_processed", "fighters_processed", "odds_processed")
