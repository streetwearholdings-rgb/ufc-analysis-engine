from datetime import date

from sqlalchemy import Date, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Event(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "events"

    external_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    event_date: Mapped[date] = mapped_column(Date, index=True)
    location: Mapped[str | None] = mapped_column(String(200))
    promotion: Mapped[str] = mapped_column(String(50), default="UFC", server_default="UFC")
