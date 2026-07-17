from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class OddsProviderEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "odds_provider_events"
    __table_args__ = (
        UniqueConstraint("provider", "provider_event_id"),
        Index("ix_odds_provider_events_commence_time", "commence_time"),
    )

    provider: Mapped[str] = mapped_column(String(50))
    provider_event_id: Mapped[str] = mapped_column(String(150), index=True)
    sport_key: Mapped[str] = mapped_column(String(100))
    home_team: Mapped[str] = mapped_column(String(200))
    away_team: Mapped[str] = mapped_column(String(200))
    commence_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    internal_event_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("events.id"), index=True)
    internal_fight_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("fights.id"), index=True)
    match_status: Mapped[str] = mapped_column(String(30), index=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
