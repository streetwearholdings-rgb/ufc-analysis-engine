from datetime import datetime

from sqlalchemy import JSON, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, UUIDPrimaryKeyMixin


class IngestionRun(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "ingestion_runs"

    provider: Mapped[str] = mapped_column(String(50), index=True)
    status: Mapped[str] = mapped_column(String(20), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    events_processed: Mapped[int] = mapped_column(Integer, default=0)
    fights_processed: Mapped[int] = mapped_column(Integer, default=0)
    fighters_processed: Mapped[int] = mapped_column(Integer, default=0)
    odds_processed: Mapped[int] = mapped_column(Integer, default=0)
    records: Mapped[dict[str, int]] = mapped_column(JSON, default=dict)
    error_summary: Mapped[str | None] = mapped_column(Text)
