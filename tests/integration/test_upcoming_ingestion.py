from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import get_settings
from app.database.base import Base
from app.database.models.event import Event
from app.database.models.fight import Fight
from app.database.models.fighter import Fighter
from app.database.models.ingestion_run import IngestionRun
from app.database.models.odds_snapshot import OddsSnapshot
from app.ingestion.service import UpcomingIngestionService, ingestion_status
from app.main import app
from app.odds.client import ProviderResult
from app.odds.exceptions import OddsProviderAuthenticationError
from app.odds.schemas import (
    ProviderBookmaker,
    ProviderEvent,
    ProviderMarket,
    ProviderOutcome,
    QuotaMetadata,
)
from app.repositories.odds import OddsRepository

NOW = datetime.now(UTC) + timedelta(days=7)


class FakeProvider:
    def __init__(self, events: list[ProviderEvent], error: Exception | None = None) -> None:
        self.events = events
        self.error = error

    def get_upcoming_moneyline_odds(self) -> ProviderResult:
        if self.error:
            raise self.error
        return ProviderResult(self.events, QuotaMetadata())


def database() -> sessionmaker[Session]:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def provider_event() -> ProviderEvent:
    market = ProviderMarket(
        key="h2h",
        last_update=NOW,
        outcomes=[
            ProviderOutcome(name="Alpha One", price=Decimal("2.1")),
            ProviderOutcome(name="Beta Two", price=Decimal("1.8")),
        ],
    )
    return ProviderEvent(
        id="ufc-bout-1",
        sport_key="mma_ufc",
        sport_title="UFC",
        commence_time=NOW,
        home_team="Alpha One",
        away_team="Beta Two",
        bookmakers=[ProviderBookmaker(key="book", title="Book", last_update=NOW, markets=[market])],
    )


def test_successful_ingestion_and_duplicate_prevention() -> None:
    factory = database()
    service = UpcomingIngestionService(FakeProvider([provider_event()]), factory)  # type: ignore[arg-type]

    first = service.ingest()
    second = service.ingest()

    assert (first.events_processed, first.fights_processed, first.fighters_processed, first.odds_processed) == (
        1,
        1,
        2,
        2,
    )
    assert first.records["events_created"] == 1
    assert second.records["events_created"] == 0
    assert second.records["fights_created"] == 0
    assert second.records["fighters_created"] == 0
    assert second.records["duplicate_odds_skipped"] == 2
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(Event)) == 1
        assert session.scalar(select(func.count()).select_from(Fight)) == 1
        assert session.scalar(select(func.count()).select_from(Fighter)) == 2
        assert session.scalar(select(func.count()).select_from(OddsSnapshot)) == 2
        fight = session.scalar(select(Fight))
        assert fight is not None and fight.weight_class is None and fight.scheduled_rounds is None


def test_empty_provider_response_is_successful() -> None:
    factory = database()
    result = UpcomingIngestionService(FakeProvider([]), factory).ingest()  # type: ignore[arg-type]
    assert result.events_processed == result.fights_processed == result.fighters_processed == 0
    with factory() as session:
        assert ingestion_status(session).last_successful_ingestion_time is not None


def test_provider_authentication_failure_is_recorded_safely() -> None:
    factory = database()
    provider = FakeProvider([], OddsProviderAuthenticationError("secret credential rejected"))
    with pytest.raises(OddsProviderAuthenticationError):
        UpcomingIngestionService(provider, factory).ingest()  # type: ignore[arg-type]
    with factory() as session:
        status = ingestion_status(session)
        assert status.last_failure_time is not None
        assert status.safe_error_summary == "Provider authentication failed."
        assert "secret" not in (status.safe_error_summary or "")


def test_database_rollback_on_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    factory = database()

    def fail_insert(repository: OddsRepository, snapshot: object) -> bool:
        raise RuntimeError("database write failed")

    monkeypatch.setattr(OddsRepository, "insert_snapshot_if_new", fail_insert)
    with pytest.raises(RuntimeError, match="database write failed"):
        UpcomingIngestionService(FakeProvider([provider_event()]), factory).ingest()  # type: ignore[arg-type]

    with factory() as session:
        assert session.scalar(select(func.count()).select_from(Event)) == 0
        assert session.scalar(select(func.count()).select_from(Fighter)) == 0
        run = session.scalar(select(IngestionRun))
        assert run is not None and run.status == "failed"


@pytest.mark.parametrize(
    "path",
    ["/api/v1/admin/ingest/upcoming", "/api/v1/admin/ingestion/status"],
)
def test_admin_ingestion_routes_require_api_key(path: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("API_KEY", "admin-test-key")
    get_settings.cache_clear()
    try:
        response = TestClient(app).request("POST" if "ingest/upcoming" in path else "GET", path)
    finally:
        get_settings.cache_clear()
    assert response.status_code == 401
