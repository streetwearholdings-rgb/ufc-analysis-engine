from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Float, ForeignKey, String, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, UUIDPrimaryKeyMixin


class FightPerformanceScore(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "fight_performance_scores"
    __table_args__ = (UniqueConstraint("fight_id", "fighter_id", "model_version"),)

    fight_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("fights.id", ondelete="CASCADE"), index=True)
    fighter_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("fighters.id"), index=True)
    opponent_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("fighters.id"))
    damage_score: Mapped[float] = mapped_column(Float)
    striking_score: Mapped[float] = mapped_column(Float)
    grappling_score: Mapped[float] = mapped_column(Float)
    control_score: Mapped[float] = mapped_column(Float)
    result_quality_score: Mapped[float] = mapped_column(Float)
    raw_performance_score: Mapped[float] = mapped_column(Float)
    opponent_adjusted_score: Mapped[float] = mapped_column(Float)
    final_performance_score: Mapped[float] = mapped_column(Float)
    model_version: Mapped[str] = mapped_column(String(50))
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
