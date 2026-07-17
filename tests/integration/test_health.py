from collections.abc import Generator

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.session import get_db
from app.main import app

engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSession = sessionmaker(bind=engine)


def override_db() -> Generator[Session, None, None]:
    with TestingSession() as session:
        yield session


def test_health_checks_database_connection() -> None:
    app.dependency_overrides[get_db] = override_db
    try:
        response = TestClient(app).get("/health")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


class UnavailableDatabase:
    def execute(self, statement: object) -> None:
        raise OperationalError("SELECT 1", {}, Exception("unavailable"))


def unavailable_db() -> Generator[Session, None, None]:
    yield UnavailableDatabase()  # type: ignore[misc]


def test_health_returns_503_without_exposing_database_error() -> None:
    app.dependency_overrides[get_db] = unavailable_db
    try:
        response = TestClient(app).get("/health")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json() == {"detail": "Database unavailable"}
    assert "SELECT 1" not in response.text
