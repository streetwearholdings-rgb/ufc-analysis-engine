from datetime import date
from uuid import UUID

from sqlalchemy import Date, Float, ForeignKey, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class FighterStyleScore(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "fighter_style_scores"
    __table_args__ = (UniqueConstraint("fighter_id", "calculation_date", "weight_class", "model_version"),)

    fighter_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("fighters.id", ondelete="CASCADE"), index=True)
    calculation_date: Mapped[date] = mapped_column(Date, index=True)
    weight_class: Mapped[str] = mapped_column(String(50))
    pressure_striking: Mapped[float] = mapped_column(Float)
    counter_striking: Mapped[float] = mapped_column(Float)
    striking_power: Mapped[float] = mapped_column(Float)
    striking_volume: Mapped[float] = mapped_column(Float)
    defensive_movement: Mapped[float] = mapped_column(Float)
    wrestling_pressure: Mapped[float] = mapped_column(Float)
    grappling_control: Mapped[float] = mapped_column(Float)
    submission_threat: Mapped[float] = mapped_column(Float)
    takedown_defence: Mapped[float] = mapped_column(Float)
    scramble_ability: Mapped[float] = mapped_column(Float)
    cardio: Mapped[float] = mapped_column(Float)
    durability: Mapped[float] = mapped_column(Float)
    pace_sustainability: Mapped[float] = mapped_column(Float)
    confidence_score: Mapped[float] = mapped_column(Float)
    model_version: Mapped[str] = mapped_column(String(50))
