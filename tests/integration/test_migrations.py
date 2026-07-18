from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from pytest import MonkeyPatch
from sqlalchemy import create_engine, inspect

from alembic import command
from app.database import models  # noqa: F401
from app.database.base import Base


def alembic_config(database_url: str) -> Config:
    config = Config(str(Path(__file__).parents[2] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def test_alembic_has_exactly_one_head() -> None:
    heads = ScriptDirectory.from_config(alembic_config("sqlite://")).get_heads()

    assert heads == ["20260718_0005"]


def test_migrations_create_every_model_table(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    database_url = f"sqlite:///{tmp_path / 'migrations.db'}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    command.upgrade(alembic_config(database_url), "head")

    inspector = inspect(create_engine(database_url))
    actual_tables = set(inspector.get_table_names())
    assert set(Base.metadata.tables).issubset(actual_tables)
    for table_name, table in Base.metadata.tables.items():
        actual_columns = {column["name"] for column in inspector.get_columns(table_name)}
        assert set(table.columns.keys()) == actual_columns
