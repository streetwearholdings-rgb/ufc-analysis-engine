from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class FighterResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    external_id: str
    first_name: str
    last_name: str
    nickname: str | None
    date_of_birth: date | None
    nationality: str | None
    stance: str | None
    height_cm: float | None
    reach_cm: float | None
    current_weight_class: str | None
    active: bool
    created_at: datetime
    updated_at: datetime
