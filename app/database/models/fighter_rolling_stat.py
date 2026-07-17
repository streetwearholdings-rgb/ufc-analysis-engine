from datetime import date
from uuid import UUID

from sqlalchemy import Date, Float, ForeignKey, Integer, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class FighterRollingStat(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "fighter_rolling_stats"
    __table_args__ = (UniqueConstraint("fighter_id", "calculation_date", "window_type", "weight_class"),)

    fighter_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("fighters.id", ondelete="CASCADE"), index=True)
    calculation_date: Mapped[date] = mapped_column(Date, index=True)
    window_type: Mapped[str] = mapped_column(String(30))
    weight_class: Mapped[str] = mapped_column(String(50))
    fights_count: Mapped[int] = mapped_column(Integer)
    rounds_count: Mapped[int] = mapped_column(Integer)
    minutes_observed: Mapped[float] = mapped_column(Float)
    significant_strikes_landed_per_minute: Mapped[float] = mapped_column(Float)
    significant_strikes_absorbed_per_minute: Mapped[float] = mapped_column(Float)
    significant_strike_differential_per_minute: Mapped[float] = mapped_column(Float)
    significant_strike_accuracy: Mapped[float] = mapped_column(Float)
    significant_strike_defence: Mapped[float] = mapped_column(Float)
    strike_attempts_per_minute: Mapped[float] = mapped_column(Float)
    knockdowns_per_15: Mapped[float] = mapped_column(Float)
    knockdowns_absorbed_per_15: Mapped[float] = mapped_column(Float)
    takedowns_landed_per_15: Mapped[float] = mapped_column(Float)
    takedown_attempts_per_15: Mapped[float] = mapped_column(Float)
    takedown_accuracy: Mapped[float] = mapped_column(Float)
    takedown_defence: Mapped[float] = mapped_column(Float)
    control_seconds_per_15: Mapped[float] = mapped_column(Float)
    control_differential_per_15: Mapped[float] = mapped_column(Float)
    submission_attempts_per_15: Mapped[float] = mapped_column(Float)
    win_rate: Mapped[float] = mapped_column(Float)
    finish_rate: Mapped[float] = mapped_column(Float)
    knockout_rate: Mapped[float] = mapped_column(Float)
    submission_rate: Mapped[float] = mapped_column(Float)
    decision_rate: Mapped[float] = mapped_column(Float)
    round_win_rate: Mapped[float] = mapped_column(Float)
    late_round_output_ratio: Mapped[float] = mapped_column(Float)
