from collections.abc import Generator
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.base import Base
from app.database.models.fight_performance_score import FightPerformanceScore
from app.database.models.fighter import Fighter
from app.database.session import get_db
from app.main import app

engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSession = sessionmaker(bind=engine, expire_on_commit=False)
Base.metadata.create_all(engine)


def override_db() -> Generator[Session, None, None]:
    with TestingSession() as session:
        yield session


def test_fighter_performances_returns_scores_and_explanations() -> None:
    fighter_id = UUID(int=901)
    with TestingSession.begin() as session:
        session.add(Fighter(id=fighter_id, external_id="fictional-901", first_name="Ari", last_name="Vale"))
        session.add(
            FightPerformanceScore(
                fight_id=UUID(int=902),
                fighter_id=fighter_id,
                opponent_id=UUID(int=903),
                damage_score=70,
                striking_score=65,
                grappling_score=40,
                control_score=35,
                result_quality_score=80,
                raw_performance_score=61.75,
                opponent_adjusted_score=61.75,
                final_performance_score=61.75,
                model_version="phase2-v1",
            )
        )
    app.dependency_overrides[get_db] = override_db
    try:
        response = TestClient(app).get(f"/api/v1/fighters/{fighter_id}/performances")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()[0]
    assert payload["damage"]["score"] == 70
    assert "knockdowns" in payload["damage"]["explanation"]
    assert payload["final_performance_score"] == 61.75


def test_unknown_fighter_returns_404() -> None:
    app.dependency_overrides[get_db] = override_db
    try:
        response = TestClient(app).get(f"/api/v1/fighters/{UUID(int=9999)}/performances")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json() == {"detail": "Fighter not found"}
