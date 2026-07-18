from enum import StrEnum
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class FightResult(StrEnum):
    FIGHTER_A_WIN = "fighter_a_win"
    FIGHTER_B_WIN = "fighter_b_win"
    DRAW = "draw"
    NO_CONTEST = "no_contest"
    OVERTURNED = "overturned"


class Fight(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "fights"
    __table_args__ = (
        CheckConstraint("fighter_a_id <> fighter_b_id", name="different_fighters"),
        CheckConstraint("scheduled_rounds > 0", name="positive_scheduled_rounds"),
        CheckConstraint("completed_rounds >= 0", name="nonnegative_completed_rounds"),
    )

    external_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    event_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("events.id"), index=True)
    fighter_a_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("fighters.id"), index=True)
    fighter_b_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("fighters.id"), index=True)
    winner_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("fighters.id"))
    loser_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("fighters.id"))
    weight_class: Mapped[str | None] = mapped_column(String(50), index=True)
    scheduled_rounds: Mapped[int | None] = mapped_column(Integer)
    completed_rounds: Mapped[int] = mapped_column(Integer, default=0)
    result: Mapped[str] = mapped_column(String(30), index=True)
    method: Mapped[str | None] = mapped_column(String(100))
    finish_round: Mapped[int | None] = mapped_column(Integer)
    finish_time_seconds: Mapped[int | None] = mapped_column(Integer)
    referee: Mapped[str | None] = mapped_column(String(100))
    is_title_fight: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    is_interim_title_fight: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    fighter_a_short_notice: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    fighter_b_short_notice: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    fighter_a_missed_weight: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    fighter_b_missed_weight: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
