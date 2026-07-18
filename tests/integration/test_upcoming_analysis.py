from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Float, Integer, create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.analysis.read_service import AnalysisReadService
from app.analysis.schemas import AnalysisFilters
from app.analysis.service import (
    CALIBRATION_STATUS,
    MODEL_TYPE,
    AnalysisAlreadyRunningError,
    UpcomingAnalysisService,
)
from app.config import Settings, get_settings
from app.database.base import Base
from app.database.models.analysis import FightAnalysis
from app.database.models.event import Event
from app.database.models.fight import Fight
from app.database.models.fighter import Fighter
from app.database.models.fighter_rating import FighterRating
from app.database.models.fighter_rolling_stat import FighterRollingStat
from app.database.models.fighter_style_score import FighterStyleScore
from app.database.models.odds_snapshot import OddsSnapshot
from app.main import app

A, B, EVENT, FIGHT = UUID(int=801), UUID(int=802), UUID(int=803), UUID(int=804)
NOW = datetime.now(UTC)


def database() -> sessionmaker[Session]:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def settings(**values: object) -> Settings:
    defaults: dict[str, object] = {
        "min_feature_quality": 0.5,
        "min_confidence_score": 0.5,
        "min_value_edge": 0.01,
        "min_expected_value": 0.01,
        "max_odds_age_minutes": 120,
        "min_recommended_odds": 1.1,
        "max_recommended_odds": 5,
    }
    return Settings(_env_file=None, **(defaults | values))


def seed(factory: sessionmaker[Session], *, profiles: bool = True, odds: bool = True, odds_age: int = 0) -> None:
    with factory.begin() as session:
        session.add_all(
            [
                Fighter(id=A, external_id="analysis-a", first_name="Alpha", last_name="One"),
                Fighter(id=B, external_id="analysis-b", first_name="Beta", last_name="Two"),
                Event(
                    id=EVENT,
                    external_id="analysis-event",
                    name="UFC Analysis",
                    event_date=date.today() + timedelta(days=2),
                ),
            ]
        )
        session.flush()
        session.add(
            Fight(
                id=FIGHT,
                external_id="analysis-fight",
                event_id=EVENT,
                fighter_a_id=A,
                fighter_b_id=B,
                weight_class="Lightweight",
                scheduled_rounds=3,
                completed_rounds=0,
                result="scheduled",
            )
        )
        if profiles:
            session.add_all([_rating(A, 1700), _rating(B, 1500), _style(A), _style(B), _stats(A), _stats(B)])
        if odds:
            updated = NOW - timedelta(minutes=odds_age)
            session.add_all([_odds(A, "2.00", updated), _odds(B, "1.90", updated)])


def test_missing_fighter_data_persists_insufficient_without_fake_probability() -> None:
    factory = database()
    seed(factory, profiles=False)
    result = UpcomingAnalysisService(factory, settings()).run()
    assert result.insufficient_data == 1 and result.recommendations_created == 0
    with factory() as session:
        analysis = session.scalar(select(FightAnalysis))
        assert analysis is not None
        assert analysis.recommendation_status == "insufficient_data"
        assert analysis.model_probability is None
        assert analysis.predicted_winner_id is None


def test_successful_run_market_math_metadata_schema_and_idempotency() -> None:
    factory = database()
    seed(factory)
    service = UpcomingAnalysisService(factory, settings())
    first = service.run(event_id=EVENT)
    second = service.run(event_id=EVENT)
    forced = service.run(event_id=EVENT, force=True)
    assert first.fights_analysed == 1 and first.recommendations_created == 1
    assert second.fights_analysed == 1
    assert forced.fights_analysed == 1
    with factory() as session:
        rows = list(session.scalars(select(FightAnalysis).order_by(FightAnalysis.generated_at)))
        assert len(rows) == 2 and sum(row.active for row in rows) == 1
        analysis = rows[-1]
        assert analysis.model_type == MODEL_TYPE
        assert analysis.calibration_status == CALIBRATION_STATUS == "uncalibrated"
        assert analysis.model_probability != Decimal("0.50000000")
        assert analysis.no_vig_market_probability == Decimal("0.48717949")
        assert analysis.value_edge == analysis.model_probability - analysis.no_vig_market_probability
        assert analysis.expected_value == analysis.model_probability * Decimal("2.0000") - Decimal(1)
        response = AnalysisReadService(session).fight(FIGHT)
        assert response.model_dump().keys() >= {
            "predicted_winner",
            "model_probability",
            "value_edge",
            "expected_value",
            "warnings",
        }
        page = AnalysisReadService(session).page(AnalysisFilters(event_id=EVENT))
        assert page.total == 1 and page.items[0].fight_id == FIGHT


@pytest.mark.parametrize(
    ("odds", "age", "reason"),
    [(False, 0, "unavailable"), (True, 180, "stale")],
)
def test_missing_or_stale_odds_produces_no_bet(odds: bool, age: int, reason: str) -> None:
    factory = database()
    seed(factory, odds=odds, odds_age=age)
    result = UpcomingAnalysisService(factory, settings()).run()
    assert result.no_bets == 1 and result.recommendations_created == 0
    with factory() as session:
        analysis = session.scalar(select(FightAnalysis))
        assert analysis is not None and reason in (analysis.no_bet_reason or "").lower()


def test_thresholds_prevent_recommendation() -> None:
    factory = database()
    seed(factory)
    restrictive = settings(min_value_edge=0.9, min_expected_value=0.9)
    result = UpcomingAnalysisService(factory, restrictive).run()
    assert result.no_bets == 1


def test_duplicate_run_lock_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    factory = database()
    seed(factory)
    monkeypatch.setattr("app.analysis.service._acquire_lock", lambda session: False)
    with pytest.raises(AnalysisAlreadyRunningError):
        UpcomingAnalysisService(factory, settings()).run()


def test_admin_authentication_and_exception_sanitization(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("API_KEY", "analysis-admin-key")
    get_settings.cache_clear()
    try:
        unauthorized = TestClient(app).post("/api/v1/admin/analysis/run-upcoming", json={})
        assert unauthorized.status_code == 401
        monkeypatch.setattr(
            UpcomingAnalysisService,
            "run",
            lambda self, **kwargs: (_ for _ in ()).throw(RuntimeError("DATABASE_URL=secret")),
        )
        failed = TestClient(app).post(
            "/api/v1/admin/analysis/run-upcoming",
            headers={"X-API-Key": "analysis-admin-key"},
            json={},
        )
        assert failed.status_code == 500
        assert failed.json() == {
            "error": "analysis_failed",
            "message": "The fight analysis could not be completed.",
        }
        assert "secret" not in failed.text
    finally:
        get_settings.cache_clear()


def _rating(fighter_id: UUID, overall: float) -> FighterRating:
    return FighterRating(
        fighter_id=fighter_id,
        rating_date=date.today(),
        weight_class="Lightweight",
        overall_rating=overall,
        striking_rating=overall,
        wrestling_rating=overall,
        submission_rating=overall,
        defensive_rating=overall,
        five_round_rating=overall,
        performance_score=70,
        confidence_score=0.9,
        sample_size=5,
        model_version="test",
    )


def _style(fighter_id: UUID) -> FighterStyleScore:
    excluded = {"id", "fighter_id", "calculation_date", "weight_class", "model_version", "created_at", "updated_at"}
    values = {column.name: 70.0 for column in FighterStyleScore.__table__.columns if column.name not in excluded}
    values["confidence_score"] = 0.9
    return FighterStyleScore(
        fighter_id=fighter_id,
        calculation_date=date.today(),
        weight_class="Lightweight",
        model_version="test",
        **values,
    )


def _stats(fighter_id: UUID) -> FighterRollingStat:
    excluded = {
        "id", "fighter_id", "calculation_date", "window_type", "weight_class", "created_at", "updated_at"
    }
    values: dict[str, float | int] = {}
    for column in FighterRollingStat.__table__.columns:
        if column.name in excluded:
            continue
        values[column.name] = 5 if isinstance(column.type, Integer) else 0.7 if isinstance(column.type, Float) else 0
    return FighterRollingStat(
        fighter_id=fighter_id,
        calculation_date=date.today(),
        window_type="career",
        weight_class="Lightweight",
        **values,
    )


def _odds(fighter_id: UUID, price: str, updated: datetime) -> OddsSnapshot:
    decimal_odds = Decimal(price)
    return OddsSnapshot(
        provider="the_odds_api",
        provider_event_id="analysis-provider",
        internal_event_id=EVENT,
        internal_fight_id=FIGHT,
        internal_fighter_id=fighter_id,
        bookmaker_key="book",
        bookmaker_name="Book",
        market_type="moneyline",
        selection_name=str(fighter_id),
        decimal_odds=decimal_odds,
        implied_probability=(Decimal(1) / decimal_odds).quantize(Decimal("0.00000001")),
        bookmaker_last_update=updated,
        captured_at=updated,
        created_at=updated,
    )
