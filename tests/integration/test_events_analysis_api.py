from collections.abc import Generator
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.dependencies as dependencies
from app.config import Settings
from app.database.base import Base
from app.database.models.context import ContextAdjustment, ContextSignal
from app.database.models.event import Event
from app.database.models.fight import Fight
from app.database.models.fighter import Fighter
from app.database.models.matchup_analysis import MatchupAnalysis
from app.database.models.odds_snapshot import OddsSnapshot
from app.database.session import get_db
from app.main import app

A, B = UUID(int=9101), UUID(int=9102)
EVENT, FIGHT, EMPTY_FIGHT = UUID(int=9201), UUID(int=9301), UUID(int=9302)
SIGNAL, REJECT_SIGNAL = UUID(int=9401), UUID(int=9402)

engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSession = sessionmaker(bind=engine, expire_on_commit=False)
Base.metadata.create_all(engine)


def override_db() -> Generator[Session, None, None]:
    with TestingSession() as session:
        yield session


def test_event_analysis_context_admin_and_openapi(monkeypatch: object) -> None:
    now = datetime.now(UTC)
    _seed(now)
    app.dependency_overrides[get_db] = override_db
    monkeypatch.setattr(dependencies, "get_settings", lambda: Settings(_env_file=None, api_key="admin-secret"))  # type: ignore[attr-defined]
    client = TestClient(app)
    try:
        upcoming = client.get("/api/v1/events/upcoming", params={"from_date": date.today().isoformat()})
        assert upcoming.status_code == 200
        assert upcoming.json()[0]["fight_count"] == 2

        card = client.get(f"/api/v1/events/{EVENT}/fights")
        assert card.status_code == 200
        assert len(card.json()["fights"]) == 2
        assert card.json()["fights"][0]["fighter_a"]["name"] == "Alpha One"

        analysis = client.get(f"/api/v1/fights/{FIGHT}/analysis")
        assert analysis.status_code == 200
        payload = analysis.json()
        assert payload["probabilities"][0]["base_probability"] == "0.58000000"
        assert payload["probabilities"][0]["context_adjusted_probability"] == "0.56000000"
        assert payload["model_confidence"] == "0.82"
        assert len(payload["best_bookmaker_odds"]) == 2
        assert payload["best_bookmaker_odds"][0]["expected_value"] == "0.12000000"
        assert payload["applied_context_signals"][0]["label"] == "short_notice_replacement"
        assert payload["excluded_context_signals"][0]["reason"] == "pending review"
        assert payload["pending_context_signals"][0]["signal_id"] == str(SIGNAL)
        assert payload["model_version"] == "phase3-v1"
        assert payload["context_engine_version"] == "phase5-v1"
        assert payload["odds_timestamp"] is not None

        pending = client.get("/api/v1/context/reviews/pending", params={"limit": 1, "offset": 0})
        assert pending.status_code == 200 and pending.json()["total"] == 2
        assert client.get("/api/v1/context/reviews/pending", params={"limit": 0}).status_code == 422

        unauthorized = client.post(
            f"/api/v1/admin/context/signals/{SIGNAL}/approve",
            json={"reviewer": "admin", "reason": "Verified"},
        )
        assert unauthorized.status_code == 401
        approved = client.post(
            f"/api/v1/admin/context/signals/{SIGNAL}/approve",
            headers={"X-API-Key": "admin-secret"},
            json={"reviewer": "admin", "reason": "Verified"},
        )
        assert approved.status_code == 200 and approved.json()["review_status"] == "approved"
        rejected = client.post(
            f"/api/v1/admin/context/signals/{REJECT_SIGNAL}/reject",
            headers={"X-API-Key": "admin-secret"},
            json={"reviewer": "admin", "reason": "Unsupported"},
        )
        assert rejected.status_code == 200 and rejected.json()["review_status"] == "rejected"

        assert client.get(f"/api/v1/fights/{EMPTY_FIGHT}/analysis").status_code == 409
        assert client.get(f"/api/v1/events/{UUID(int=999999)}/fights").status_code == 404
        assert client.get("/api/v1/events/not-a-uuid/fights").status_code == 422

        openapi = client.get("/openapi.json").json()
        schemes = openapi["components"]["securitySchemes"]
        assert schemes["APIKeyHeader"]["name"] == "X-API-Key"
        approve_operation = openapi["paths"]["/api/v1/admin/context/signals/{signal_id}/approve"]["post"]
        assert approve_operation["security"] == [{"APIKeyHeader": []}]
    finally:
        app.dependency_overrides.clear()


def _seed(now: datetime) -> None:
    with TestingSession.begin() as session:
        session.query(ContextAdjustment).delete()
        session.query(ContextSignal).delete()
        session.query(OddsSnapshot).delete()
        session.query(MatchupAnalysis).delete()
        session.query(Fight).delete()
        session.query(Event).delete()
        session.query(Fighter).delete()
        session.add_all(
            [
                Fighter(
                    id=A, external_id="api-a", first_name="Alpha", last_name="One", current_weight_class="Lightweight"
                ),
                Fighter(
                    id=B, external_id="api-b", first_name="Beta", last_name="Two", current_weight_class="Lightweight"
                ),
                Event(id=EVENT, external_id="api-event", name="UFC API", event_date=date.today() + timedelta(days=2)),
            ]
        )
        session.flush()
        session.add_all([_fight(FIGHT, "api-fight"), _fight(EMPTY_FIGHT, "empty-fight")])
        session.flush()
        session.add(
            MatchupAnalysis(
                fighter_a_id=A,
                fighter_b_id=B,
                weight_class="Lightweight",
                analysis_date=date.today(),
                fighter_a_overall_advantage=5,
                fighter_a_striking_advantage=4,
                fighter_a_wrestling_advantage=3,
                fighter_a_submission_advantage=2,
                fighter_a_cardio_advantage=1,
                fighter_a_durability_advantage=1,
                confidence_score=0.82,
                key_interactions=[],
                model_version="phase3-v1",
            )
        )
        session.add_all(
            [
                _adjustment(A, Decimal("0.58"), Decimal("0.56"), now),
                _adjustment(B, Decimal("0.42"), Decimal("0.44"), now),
                _odds(A, "2.00", now),
                _odds(B, "1.90", now),
                _signal(SIGNAL, A, "short_notice"),
                _signal(REJECT_SIGNAL, B, "injury"),
            ]
        )


def _fight(fight_id: UUID, external_id: str) -> Fight:
    return Fight(
        id=fight_id,
        external_id=external_id,
        event_id=EVENT,
        fighter_a_id=A,
        fighter_b_id=B,
        weight_class="Lightweight",
        scheduled_rounds=3,
        completed_rounds=0,
        result="scheduled",
    )


def _adjustment(fighter_id: UUID, base: Decimal, final: Decimal, now: datetime) -> ContextAdjustment:
    explanation = {
        "explanation_items": [{"signal_id": str(SIGNAL), "label": "short_notice_replacement"}],
        "signals_excluded": [{"signal_id": str(REJECT_SIGNAL), "reason": "pending review"}],
        "warnings": [],
    }
    return ContextAdjustment(
        fighter_id=fighter_id,
        fight_id=FIGHT,
        base_probability=base,
        raw_context_score=Decimal("-0.5"),
        requested_adjustment=final - base,
        applied_adjustment=final - base,
        final_probability=final,
        context_confidence=Decimal("0.9"),
        calculation_version="phase5-v1",
        calculated_at=now,
        explanation_json=explanation,
        created_at=now,
    )


def _odds(fighter_id: UUID, price: str, now: datetime) -> OddsSnapshot:
    decimal_odds = Decimal(price)
    return OddsSnapshot(
        provider="the_odds_api",
        provider_event_id="provider-api",
        internal_event_id=EVENT,
        internal_fight_id=FIGHT,
        internal_fighter_id=fighter_id,
        bookmaker_key="book",
        bookmaker_name="Book",
        market_type="moneyline",
        selection_name=str(fighter_id),
        decimal_odds=decimal_odds,
        implied_probability=(Decimal(1) / decimal_odds).quantize(Decimal("0.00000001")),
        bookmaker_last_update=now,
        captured_at=now,
        created_at=now,
    )


def _signal(signal_id: UUID, fighter_id: UUID, category: str) -> ContextSignal:
    now = datetime.now(UTC)
    return ContextSignal(
        id=signal_id,
        fighter_id=fighter_id,
        fight_id=FIGHT,
        event_id=EVENT,
        category=category,
        label="short_notice_replacement" if category == "short_notice" else "confirmed_injury",
        direction="negative",
        severity=Decimal("0.8"),
        confidence=Decimal("0.8"),
        source_reliability=Decimal("0.8"),
        occurred_at=now,
        review_status="pending",
        claim_type="credible_report",
        extraction_method="manual",
        deduplication_key=f"api-{signal_id}",
        is_contradicted=False,
    )
