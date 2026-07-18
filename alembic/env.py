import logging
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context
from app.config import Settings
from app.database import models  # noqa: F401
from app.database.base import Base

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)
logger = logging.getLogger("alembic.env")

# Settings reads DATABASE_URL and normalises Render's postgres:// (and the
# driver-less postgresql:// form) to SQLAlchemy's psycopg2 URL. Escape percent
# signs because Alembic's Config uses interpolation internally.
database_url = Settings().database_url
config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
        compare_server_default=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    logger.info("Running database migrations using configured DATABASE_URL")
    connectable = engine_from_config(
        config.get_section(config.config_ini_section) or {},
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )
        with context.begin_transaction():
            context.run_migrations()
    logger.info("Database migrations completed successfully")


run_migrations_offline() if context.is_offline_mode() else run_migrations_online()
