from datetime import date
from uuid import UUID

from sqlalchemy import JSON, Date, Float, ForeignKey, String, UniqueConstraint, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class MatchupAnalysis(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "matchup_analysis"
    __table_args__ = (
        UniqueConstraint("fighter_a_id", "fighter_b_id", "weight_class", "analysis_date", "model_version"),
    )

    fighter_a_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("fighters.id"), index=True)
    fighter_b_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("fighters.id"), index=True)
    weight_class: Mapped[str] = mapped_column(String(50))
    analysis_date: Mapped[date] = mapped_column(Date, index=True)
    fighter_a_overall_advantage: Mapped[float] = mapped_column(Float)
    fighter_a_striking_advantage: Mapped[float] = mapped_column(Float)
    fighter_a_wrestling_advantage: Mapped[float] = mapped_column(Float)
    fighter_a_submission_advantage: Mapped[float] = mapped_column(Float)
    fighter_a_cardio_advantage: Mapped[float] = mapped_column(Float)
    fighter_a_durability_advantage: Mapped[float] = mapped_column(Float)
    confidence_score: Mapped[float] = mapped_column(Float)
    key_interactions: Mapped[list[dict[str, object]]] = mapped_column(JSON().with_variant(JSONB, "postgresql"))
    model_version: Mapped[str] = mapped_column(String(50))
