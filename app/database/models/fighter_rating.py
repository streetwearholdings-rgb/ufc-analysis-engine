from datetime import date
from uuid import UUID

from sqlalchemy import Date, Float, ForeignKey, Integer, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class FighterRating(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "fighter_ratings"
    __table_args__ = (UniqueConstraint("fighter_id", "rating_date", "weight_class", "model_version"),)

    fighter_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("fighters.id", ondelete="CASCADE"), index=True)
    rating_date: Mapped[date] = mapped_column(Date, index=True)
    weight_class: Mapped[str] = mapped_column(String(50))
    overall_rating: Mapped[float] = mapped_column(Float)
    striking_rating: Mapped[float] = mapped_column(Float)
    wrestling_rating: Mapped[float] = mapped_column(Float)
    submission_rating: Mapped[float] = mapped_column(Float)
    defensive_rating: Mapped[float] = mapped_column(Float)
    five_round_rating: Mapped[float] = mapped_column(Float)
    performance_score: Mapped[float] = mapped_column(Float)
    confidence_score: Mapped[float] = mapped_column(Float)
    sample_size: Mapped[int] = mapped_column(Integer)
    model_version: Mapped[str] = mapped_column(String(50))
