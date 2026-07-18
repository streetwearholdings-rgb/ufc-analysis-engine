from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

import httpx
import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings
from app.database.base import Base
from app.database.models.event import Event
from app.database.models.fight import Fight
from app.database.models.fighter import Fighter
from app.database.models.odds_provider_event import OddsProviderEvent
from app.database.models.odds_snapshot import OddsSnapshot
from app.odds.client import OddsApiClient
from app.odds.exceptions import (
    OddsProviderAuthenticationError,
    OddsProviderConfigurationError,
    OddsProviderRateLimitError,
    OddsProviderResponseError,
)
from app.odds.matching import match_provider_event, normalise_fighter_name
from app.odds.schemas import NormalisedOddsSnapshot, ProviderEvent, ProviderOutcome, QuotaMetadata
from app.repositories.odds import OddsRepository
from app.services.odds_ingestion_service import OddsIngestionService
from app.services.odds_market_service import OddsMarketService

A, B = UUID(int=501), UUID(int=502)
EVENT_ID, FIGHT_ID = UUID(int=601), UUID(int=701)
NOW = datetime(2026, 8, 1, 10, tzinfo=UTC)


def test_configuration_defaults_regions_and_validation() -> None:
    settings = Settings(_env_file=None, odds_api_key="secret", odds_api_regions="au,us")
    assert settings.odds_api_regions == ["au", "us"]
    assert settings.odds_api_odds_format == "decimal"
    with pytest.raises(ValidationError):
        Settings(_env_file=None, odds_api_timeout_seconds=0)
    with pytest.raises(ValidationError):
        Settings(_env_file=None, odds_api_max_retries=-1)
    with pytest.raises(OddsProviderConfigurationError, match="ODDS_API_KEY"):
        OddsApiClient(Settings(_env_file=None, odds_api_key=None))


def test_render_database_url_cors_alias_and_production_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DATABASE_URL", "postgres://render:secret@host/database")
    monkeypatch.setenv("API_KEY", "admin-secret")
    monkeypatch.setenv("ODDS_API_KEY", "odds-secret")
    monkeypatch.setenv("CORS_ORIGINS", "https://example.test,https://admin.example.test")
    settings = Settings(_env_file=None)
    assert settings.database_url == "postgresql+psycopg2://render:secret@host/database"
    assert settings.cors_allowed_origins == ["https://example.test", "https://admin.example.test"]
    monkeypatch.delenv("DATABASE_URL")
    monkeypatch.delenv("API_KEY")
    with pytest.raises(ValidationError, match="DATABASE_URL"):
        Settings(_env_file=None, app_env="production", api_key="secret")
    with pytest.raises(ValidationError, match="API_KEY"):
        Settings(
            _env_file=None,
            app_env="production",
            database_url="postgresql://user:pass@host/db",
            odds_api_key="odds-secret",
        )


def test_client_discovers_once_parses_quota_and_skips_bad_outcome() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if request.url.path == "/v4/sports":
            return httpx.Response(200, json=[{"key": "mma_mixed_martial_arts", "active": True}])
        return httpx.Response(
            200,
            headers={"x-requests-remaining": "99", "x-requests-used": "2", "x-requests-last": "1"},
            json=[_provider_payload(invalid_outcome=True)],
        )

    client = _client(handler)
    first = client.get_upcoming_moneyline_odds()
    second = client.get_upcoming_moneyline_odds()
    assert calls.count("/v4/sports") == 1
    assert first.quota.requests_remaining == 99
    assert first.invalid_records == 1
    assert len(first.events[0].bookmakers[0].markets[0].outcomes) == 2
    assert len(second.events) == 1


@pytest.mark.parametrize("status,error", [(401, OddsProviderAuthenticationError), (429, OddsProviderRateLimitError)])
def test_client_maps_authentication_and_rate_limit(status: int, error: type[Exception]) -> None:
    client = _client(lambda request: httpx.Response(status, request=request), retries=0, sport_key="mma_ufc")
    with pytest.raises(error):
        client.get_upcoming_moneyline_odds()


def test_client_retries_server_errors_and_timeouts(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.odds.client.time.sleep", lambda _: None)
    count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal count
        count += 1
        if count == 1:
            raise httpx.ReadTimeout("timeout", request=request)
        if count == 2:
            return httpx.Response(503, request=request)
        return httpx.Response(200, request=request, json=[])

    assert _client(handler, retries=2, sport_key="mma_ufc").get_upcoming_moneyline_odds().events == []
    assert count == 3


def test_client_rejects_invalid_json_and_structure_without_key_in_error() -> None:
    client = _client(lambda request: httpx.Response(200, request=request, content=b"not-json"), sport_key="mma_ufc")
    with pytest.raises(OddsProviderResponseError) as captured:
        client.get_upcoming_moneyline_odds()
    assert "test-secret" not in str(captured.value)


def test_provider_decimal_timestamp_and_positive_price() -> None:
    event = ProviderEvent.model_validate(_provider_payload())
    assert event.commence_time.tzinfo is not None
    assert event.bookmakers[0].markets[0].outcomes[0].price == Decimal("2.50")
    with pytest.raises(ValidationError):
        ProviderOutcome(name="Bad", price=Decimal("0"))


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (" José  Aldo ", "jose aldo"),
        ('Alex "Poatan" Pereira', "alex pereira"),
        ("Dricus Du-Plessis", "dricus du plessis"),
        ("Sean O'Malley.", "sean omalley"),
    ],
)
def test_name_normalisation(raw: str, expected: str) -> None:
    assert normalise_fighter_name(raw) == expected


def test_matching_reversed_unmatched_and_ambiguous() -> None:
    event, fight, fighter_a, fighter_b = _entities()
    provider = ProviderEvent.model_validate(_provider_payload(home="Beta Two", away="Alpha One"))
    matched = match_provider_event(provider, [(fight, event, fighter_a, fighter_b)], tolerance_hours=24)
    assert matched.status == "matched" and matched.selections == {"Beta Two": B, "Alpha One": A}
    far = provider.model_copy(update={"commence_time": NOW + timedelta(days=5)})
    assert (
        match_provider_event(far, [(fight, event, fighter_a, fighter_b)], tolerance_hours=24).status
        == "unmatched_event"
    )
    assert (
        match_provider_event(provider, [(fight, event, fighter_a, fighter_b)] * 2, tolerance_hours=24).status
        == "ambiguous_event"
    )


def test_persistence_history_latest_best_stale_and_unmatched() -> None:
    factory = _database()
    _seed(factory)
    with factory.begin() as session:
        repository = OddsRepository(session)
        repository.upsert_provider_event(now=NOW, **_provider_event_values("matched"))
        first = _snapshot(price="2.50", bookmaker="a", update=NOW)
        assert repository.insert_snapshot_if_new(first)
        assert not repository.insert_snapshot_if_new(first)
        assert repository.insert_snapshot_if_new(
            _snapshot(price="2.60", bookmaker="a", update=NOW + timedelta(minutes=1))
        )
        assert repository.insert_snapshot_if_new(
            _snapshot(price="2.70", bookmaker="b", update=NOW - timedelta(hours=2))
        )
        assert repository.insert_snapshot_if_new(_snapshot(price="1.50", bookmaker="a", update=NOW, fighter_id=B))
        assert repository.insert_snapshot_if_new(_snapshot(price="3.00", bookmaker="x", update=NOW, fighter_id=None))
        best = repository.get_best_moneyline_odds_for_fight(FIGHT_ID)
        assert {row.internal_fighter_id: row.decimal_odds for row in best}[A] == Decimal("2.7000")
        fresh = repository.get_best_moneyline_odds_for_fight(FIGHT_ID, updated_after=NOW - timedelta(minutes=30))
        assert {row.internal_fighter_id: row.decimal_odds for row in fresh}[A] == Decimal("2.6000")
        assert len(repository.get_odds_history_for_fight(FIGHT_ID)) == 4
    with factory.begin() as session:
        repository = OddsRepository(session)
        repository.upsert_provider_event(now=NOW + timedelta(minutes=2), **_provider_event_values("unmatched_event"))
        row = session.scalar(select(OddsProviderEvent))
        assert row is not None and row.last_seen_at != row.first_seen_at and row.match_status == "unmatched_event"


def test_ingestion_is_idempotent_dry_run_and_market_read() -> None:
    factory = _database()
    _seed(factory)
    provider = _FakeProvider([ProviderEvent.model_validate(_provider_payload())])
    settings = Settings(_env_file=None, odds_api_key="secret", odds_api_stale_after_minutes=60_000)
    service = OddsIngestionService(provider, factory, settings)  # type: ignore[arg-type]
    dry = service.ingest_upcoming_ufc_odds(dry_run=True)
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(OddsSnapshot)) == 0
    first = service.ingest_upcoming_ufc_odds()
    second = service.ingest_upcoming_ufc_odds()
    assert dry.snapshots_inserted == 0
    assert first.provider_events_matched == 1 and first.snapshots_inserted == 2
    assert second.duplicate_snapshots_skipped == 2
    with factory() as session:
        market = OddsMarketService(session, settings).get_fight_market_odds(FIGHT_ID)
        assert len(market.selections) == 2
        assert {item.fighter_id: item.raw_implied_probability for item in market.selections}[A] == Decimal("0.40000000")


class _FakeProvider:
    def __init__(self, events: list[ProviderEvent]) -> None:
        self.events = events

    def get_upcoming_moneyline_odds(self) -> object:
        from app.odds.client import ProviderResult

        return ProviderResult(self.events, QuotaMetadata(requests_remaining=50))


def _client(handler: object, *, retries: int = 0, sport_key: str | None = None) -> OddsApiClient:
    transport = httpx.MockTransport(handler)  # type: ignore[arg-type]
    settings = Settings(
        _env_file=None,
        odds_api_key="test-secret",
        odds_api_max_retries=retries,
        odds_api_sport_key=sport_key,
    )
    return OddsApiClient(settings, httpx.Client(transport=transport))


def _provider_payload(
    *, home: str = "Alpha One", away: str = "Beta Two", invalid_outcome: bool = False
) -> dict[str, object]:
    outcomes: list[dict[str, object]] = [{"name": home, "price": "2.50"}, {"name": away, "price": "1.50"}]
    if invalid_outcome:
        outcomes.append({"name": "Bad", "price": 0})
    return {
        "id": "provider-1",
        "sport_key": "mma_ufc",
        "sport_title": "UFC",
        "commence_time": NOW.isoformat(),
        "home_team": home,
        "away_team": away,
        "bookmakers": [
            {
                "key": "sportsbet",
                "title": "Sportsbet",
                "last_update": NOW.isoformat(),
                "markets": [
                    {"key": "h2h", "last_update": NOW.isoformat(), "outcomes": outcomes},
                    {"key": "totals", "last_update": NOW.isoformat(), "outcomes": outcomes},
                ],
            }
        ],
    }


def _entities() -> tuple[Event, Fight, Fighter, Fighter]:
    event = Event(id=EVENT_ID, external_id="event", name="UFC Test", event_date=NOW.date())
    a = Fighter(id=A, external_id="a", first_name="Alpha", last_name="One")
    b = Fighter(id=B, external_id="b", first_name="Beta", last_name="Two")
    fight = Fight(
        id=FIGHT_ID,
        external_id="fight",
        event_id=EVENT_ID,
        fighter_a_id=A,
        fighter_b_id=B,
        weight_class="Lightweight",
        scheduled_rounds=3,
        completed_rounds=0,
        result="scheduled",
    )
    return event, fight, a, b


def _database() -> sessionmaker[Session]:
    return sessionmaker(bind=create_engine("sqlite:///:memory:"), expire_on_commit=False)


def _seed(factory: sessionmaker[Session]) -> None:
    Base.metadata.create_all(factory.kw["bind"])
    event, fight, a, b = _entities()
    with factory.begin() as session:
        session.add_all([a, b, event])
        session.flush()
        session.add(fight)


def _provider_event_values(status: str) -> dict[str, object]:
    return {
        "provider": "the_odds_api",
        "provider_event_id": "provider-1",
        "sport_key": "mma_ufc",
        "home_team": "Alpha One",
        "away_team": "Beta Two",
        "commence_time": NOW,
        "internal_event_id": EVENT_ID if status == "matched" else None,
        "internal_fight_id": FIGHT_ID if status == "matched" else None,
        "match_status": status,
    }


def _snapshot(*, price: str, bookmaker: str, update: datetime, fighter_id: UUID | None = A) -> NormalisedOddsSnapshot:
    decimal_odds = Decimal(price)
    return NormalisedOddsSnapshot(
        provider_event_id="provider-1",
        internal_event_id=EVENT_ID,
        internal_fight_id=FIGHT_ID,
        internal_fighter_id=fighter_id,
        sport_key="mma_ufc",
        commence_time=NOW,
        bookmaker_key=bookmaker,
        bookmaker_name=bookmaker.title(),
        selection_name="Alpha One",
        decimal_odds=decimal_odds,
        implied_probability=(Decimal(1) / decimal_odds).quantize(Decimal("0.00000001")),
        bookmaker_last_update=update,
        captured_at=NOW,
    )
