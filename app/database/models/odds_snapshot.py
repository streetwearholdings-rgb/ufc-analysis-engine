from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, UUIDPrimaryKeyMixin


class OddsSnapshot(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "odds_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "provider", "provider_event_id", "bookmaker_key", "market_type",
            "selection_name", "decimal_odds", "bookmaker_last_update",
            name="uq_odds_snapshot_provider_update",
        ),
        Index("ix_odds_snapshots_fight_market_update", "internal_fight_id", "market_type", "bookmaker_last_update"),
        Index("ix_odds_snapshots_captured_at", "captured_at"),
    )

    provider: Mapped[str] = mapped_column(String(50))
    provider_event_id: Mapped[str] = mapped_column(String(150), index=True)
    internal_event_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("events.id"), index=True)
    internal_fight_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("fights.id"), index=True)
    internal_fighter_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("fighters.id"), index=True)
    bookmaker_key: Mapped[str] = mapped_column(String(100))
    bookmaker_name: Mapped[str] = mapped_column(String(150))
    market_type: Mapped[str] = mapped_column(String(30))
    selection_name: Mapped[str] = mapped_column(String(200))
    decimal_odds: Mapped[Decimal] = mapped_column(Numeric(10, 4))
    implied_probability: Mapped[Decimal] = mapped_column(Numeric(12, 8))
    bookmaker_last_update: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
