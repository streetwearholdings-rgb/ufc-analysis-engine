from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, UUIDPrimaryKeyMixin


class FightRoundStat(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "fight_round_stats"
    __table_args__ = (
        UniqueConstraint("fight_id", "fighter_id", "round_number"),
        CheckConstraint("round_number > 0", name="positive_round_number"),
        CheckConstraint("round_duration_seconds >= 0", name="nonnegative_duration"),
    )

    fight_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("fights.id", ondelete="CASCADE"), index=True)
    fighter_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("fighters.id"), index=True)
    opponent_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("fighters.id"), index=True)
    round_number: Mapped[int] = mapped_column(Integer)
    round_duration_seconds: Mapped[int] = mapped_column(Integer)
    knockdowns: Mapped[int] = mapped_column(Integer, default=0)
    significant_strikes_landed: Mapped[int] = mapped_column(Integer, default=0)
    significant_strikes_attempted: Mapped[int] = mapped_column(Integer, default=0)
    total_strikes_landed: Mapped[int] = mapped_column(Integer, default=0)
    total_strikes_attempted: Mapped[int] = mapped_column(Integer, default=0)
    head_landed: Mapped[int] = mapped_column(Integer, default=0)
    head_attempted: Mapped[int] = mapped_column(Integer, default=0)
    body_landed: Mapped[int] = mapped_column(Integer, default=0)
    body_attempted: Mapped[int] = mapped_column(Integer, default=0)
    leg_landed: Mapped[int] = mapped_column(Integer, default=0)
    leg_attempted: Mapped[int] = mapped_column(Integer, default=0)
    distance_landed: Mapped[int] = mapped_column(Integer, default=0)
    distance_attempted: Mapped[int] = mapped_column(Integer, default=0)
    clinch_landed: Mapped[int] = mapped_column(Integer, default=0)
    clinch_attempted: Mapped[int] = mapped_column(Integer, default=0)
    ground_landed: Mapped[int] = mapped_column(Integer, default=0)
    ground_attempted: Mapped[int] = mapped_column(Integer, default=0)
    takedowns_landed: Mapped[int] = mapped_column(Integer, default=0)
    takedowns_attempted: Mapped[int] = mapped_column(Integer, default=0)
    submission_attempts: Mapped[int] = mapped_column(Integer, default=0)
    reversals: Mapped[int] = mapped_column(Integer, default=0)
    control_time_seconds: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
