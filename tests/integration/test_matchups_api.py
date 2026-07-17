from collections.abc import Generator
from datetime import date
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.base import Base
from app.database.models.fighter import Fighter
from app.database.models.fighter_rating import FighterRating
from app.database.models.fighter_style_score import FighterStyleScore
from app.database.session import get_db
from app.main import app

engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSession = sessionmaker(bind=engine)
Base.metadata.create_all(engine)


def override_db() -> Generator[Session, None, None]:
    with TestingSession() as session:
        yield session


def test_matchup_endpoint_returns_explainable_comparison() -> None:
    fighter_a_id = UUID(int=8001)
    fighter_b_id = UUID(int=8002)
    with TestingSession.begin() as session:
        session.add_all(
            [
                Fighter(id=fighter_a_id, external_id="matchup-a", first_name="Ari", last_name="Vale"),
                Fighter(id=fighter_b_id, external_id="matchup-b", first_name="Bo", last_name="North"),
                _rating(fighter_a_id, overall=1580, striking=1570, wrestling=1550),
                _rating(fighter_b_id, overall=1500, striking=1490, wrestling=1510),
                _style(fighter_a_id, pressure=75, power=80, cardio=75),
                _style(fighter_b_id, pressure=45, power=50, cardio=55),
            ]
        )
    app.dependency_overrides[get_db] = override_db
    try:
        response = TestClient(app).get(f"/api/v1/matchups/{fighter_a_id}/{fighter_b_id}")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["fighter_a"]["name"] == "Ari Vale"
    assert payload["comparison"]["overall"]["fighter"] == "fighter_a"
    assert len(payload["key_interactions"]) == 4
    assert all(item["explanation"] for item in payload["key_interactions"])
    assert payload["confidence"]["category"] == "high"


def _rating(fighter_id: UUID, *, overall: float, striking: float, wrestling: float) -> FighterRating:
    return FighterRating(
        fighter_id=fighter_id,
        rating_date=date(2026, 7, 1),
        weight_class="Lightweight",
        overall_rating=overall,
        striking_rating=striking,
        wrestling_rating=wrestling,
        submission_rating=1520,
        defensive_rating=1530,
        five_round_rating=1500,
        performance_score=65,
        confidence_score=0.85,
        sample_size=8,
        model_version="phase2-v1",
    )


def _style(fighter_id: UUID, *, pressure: float, power: float, cardio: float) -> FighterStyleScore:
    return FighterStyleScore(
        fighter_id=fighter_id,
        calculation_date=date(2026, 7, 1),
        weight_class="Lightweight",
        pressure_striking=pressure,
        counter_striking=60,
        striking_power=power,
        striking_volume=65,
        defensive_movement=60,
        wrestling_pressure=60,
        grappling_control=60,
        submission_threat=55,
        takedown_defence=65,
        scramble_ability=60,
        cardio=cardio,
        durability=70,
        pace_sustainability=65,
        confidence_score=0.82,
        model_version="phase2-v1",
    )
