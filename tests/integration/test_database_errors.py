from collections.abc import Generator

from fastapi.testclient import TestClient
from pytest import LogCaptureFixture
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.main import app


class BrokenDatabase:
    def get(self, entity: object, identifier: object) -> None:
        raise ProgrammingError(
            "SELECT * FROM missing_table",
            {},
            Exception("password=do-not-leak relation missing_table does not exist"),
        )


def broken_db() -> Generator[Session, None, None]:
    yield BrokenDatabase()  # type: ignore[misc]


def test_database_exception_returns_safe_consistent_response(caplog: LogCaptureFixture) -> None:
    app.dependency_overrides[get_db] = broken_db
    try:
        response = TestClient(app, raise_server_exceptions=False).get(
            "/api/v1/fighters/00000000-0000-0000-0000-000000000001"
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 500
    assert response.json() == {
        "error": "database_error",
        "message": "The analysis service could not complete the database operation.",
    }
    assert "do-not-leak" not in response.text
    assert "missing_table" not in response.text
    assert "traceback" not in response.text.lower()
    assert "do-not-leak" not in caplog.text
