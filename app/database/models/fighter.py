from datetime import date

from sqlalchemy import Boolean, Date, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Fighter(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "fighters"

    external_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100), index=True)
    nickname: Mapped[str | None] = mapped_column(String(100))
    date_of_birth: Mapped[date | None] = mapped_column(Date)
    nationality: Mapped[str | None] = mapped_column(String(100))
    stance: Mapped[str | None] = mapped_column(String(30))
    height_cm: Mapped[float | None] = mapped_column(Float)
    reach_cm: Mapped[float | None] = mapped_column(Float)
    current_weight_class: Mapped[str | None] = mapped_column(String(50), index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
