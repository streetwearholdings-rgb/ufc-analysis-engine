from uuid import UUID

from pydantic import BaseModel


class CalculationResponse(BaseModel):
    fighter_id: UUID
    windows_rebuilt: list[str]


class RebuildResponse(BaseModel):
    fighters_processed: int
    fighters_failed: int
