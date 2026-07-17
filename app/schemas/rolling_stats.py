from datetime import date
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class RollingStatResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    fighter_id: UUID
    calculation_date: date
    window_type: str
    weight_class: str
    fights_count: int
    rounds_count: int
    minutes_observed: float
    significant_strikes_landed_per_minute: float
    significant_strikes_absorbed_per_minute: float
    significant_strike_differential_per_minute: float
    significant_strike_accuracy: float
    significant_strike_defence: float
    strike_attempts_per_minute: float
    knockdowns_per_15: float
    knockdowns_absorbed_per_15: float
    takedowns_landed_per_15: float
    takedown_attempts_per_15: float
    takedown_accuracy: float
    takedown_defence: float
    control_seconds_per_15: float
    control_differential_per_15: float
    submission_attempts_per_15: float
    win_rate: float
    finish_rate: float
    knockout_rate: float
    submission_rate: float
    decision_rate: float
    round_win_rate: float
    late_round_output_ratio: float
