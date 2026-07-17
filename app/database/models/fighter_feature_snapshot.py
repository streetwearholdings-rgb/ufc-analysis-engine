from datetime import date
from uuid import UUID

from sqlalchemy import Date, Float, ForeignKey, Index, Integer, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class FighterFeatureSnapshot(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "fighter_feature_snapshots"
    __table_args__ = (
        UniqueConstraint("fighter_id", "source_fight_id"),
        Index("ix_feature_snapshot_fighter_date", "fighter_id", "snapshot_date"),
    )

    fighter_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("fighters.id", ondelete="CASCADE"), index=True)
    snapshot_date: Mapped[date] = mapped_column(Date, index=True)
    source_fight_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("fights.id", ondelete="CASCADE"), index=True)
    fights_completed: Mapped[int] = mapped_column(Integer)
    wins: Mapped[int] = mapped_column(Integer)
    losses: Mapped[int] = mapped_column(Integer)
    draws: Mapped[int] = mapped_column(Integer)
    elo_rating: Mapped[float] = mapped_column(Float)
    striking_score: Mapped[float] = mapped_column(Float)
    grappling_score: Mapped[float] = mapped_column(Float)
    defence_score: Mapped[float] = mapped_column(Float)
    performance_score: Mapped[float] = mapped_column(Float)
    recent_form_score: Mapped[float] = mapped_column(Float)
    strength_of_schedule: Mapped[float] = mapped_column(Float)
    finish_rate: Mapped[float] = mapped_column(Float)
    average_fight_time: Mapped[float] = mapped_column(Float)
    days_since_last_fight: Mapped[int | None] = mapped_column(Integer)
    data_quality_score: Mapped[float] = mapped_column(Float)
