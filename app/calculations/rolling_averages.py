from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from uuid import UUID

from app.database.models.fight import Fight, FightResult
from app.database.models.fight_round_stat import FightRoundStat


class RollingWindow(StrEnum):
    LAST_3 = "last_3"
    LAST_5 = "last_5"

    @property
    def fight_limit(self) -> int:
        return 3 if self is RollingWindow.LAST_3 else 5


@dataclass(frozen=True, slots=True)
class FightStatLine:
    fight_id: UUID
    event_date: date
    result: str
    won: bool
    method: str | None
    elapsed_seconds: int
    rounds_observed: int
    significant_strikes_landed: int
    significant_strikes_attempted: int
    significant_strikes_absorbed: int
    opponent_significant_strikes_attempted: int
    knockdowns: int
    knockdowns_absorbed: int
    takedowns_landed: int
    takedowns_attempted: int
    opponent_takedowns_landed: int
    opponent_takedowns_attempted: int
    control_time_seconds: int
    opponent_control_time_seconds: int
    submission_attempts: int
    early_output: int
    early_seconds: int
    late_output: int
    late_seconds: int


@dataclass(frozen=True, slots=True)
class RollingMetrics:
    window_type: RollingWindow
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
    late_round_output_ratio: float


def safe_ratio(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator > 0 else 0.0


def build_fight_stat_line(
    fighter_id: UUID,
    fight: Fight,
    event_date: date,
    rows: list[FightRoundStat],
) -> FightStatLine:
    own = [row for row in rows if row.fighter_id == fighter_id]
    opponent = [row for row in rows if row.fighter_id != fighter_id]
    return FightStatLine(
        fight_id=fight.id,
        event_date=event_date,
        result=fight.result,
        won=fight.winner_id == fighter_id,
        method=fight.method,
        elapsed_seconds=sum(row.round_duration_seconds for row in own),
        rounds_observed=len(own),
        significant_strikes_landed=sum(row.significant_strikes_landed for row in own),
        significant_strikes_attempted=sum(row.significant_strikes_attempted for row in own),
        significant_strikes_absorbed=sum(row.significant_strikes_landed for row in opponent),
        opponent_significant_strikes_attempted=sum(row.significant_strikes_attempted for row in opponent),
        knockdowns=sum(row.knockdowns for row in own),
        knockdowns_absorbed=sum(row.knockdowns for row in opponent),
        takedowns_landed=sum(row.takedowns_landed for row in own),
        takedowns_attempted=sum(row.takedowns_attempted for row in own),
        opponent_takedowns_landed=sum(row.takedowns_landed for row in opponent),
        opponent_takedowns_attempted=sum(row.takedowns_attempted for row in opponent),
        control_time_seconds=sum(row.control_time_seconds for row in own),
        opponent_control_time_seconds=sum(row.control_time_seconds for row in opponent),
        submission_attempts=sum(row.submission_attempts for row in own),
        early_output=sum(row.significant_strikes_landed for row in own if row.round_number < 3),
        early_seconds=sum(row.round_duration_seconds for row in own if row.round_number < 3),
        late_output=sum(row.significant_strikes_landed for row in own if row.round_number >= 3),
        late_seconds=sum(row.round_duration_seconds for row in own if row.round_number >= 3),
    )


def calculate_rolling_metrics(
    fights: list[FightStatLine],
    window: RollingWindow,
) -> RollingMetrics:
    selected = sorted(fights, key=lambda fight: (fight.event_date, str(fight.fight_id)), reverse=True)[
        : window.fight_limit
    ]
    elapsed_seconds = sum(fight.elapsed_seconds for fight in selected)
    scale_per_minute = safe_ratio(60.0, elapsed_seconds)
    scale_per_15 = safe_ratio(900.0, elapsed_seconds)

    landed = sum(fight.significant_strikes_landed for fight in selected)
    attempted = sum(fight.significant_strikes_attempted for fight in selected)
    absorbed = sum(fight.significant_strikes_absorbed for fight in selected)
    opponent_attempted = sum(fight.opponent_significant_strikes_attempted for fight in selected)
    takedowns_landed = sum(fight.takedowns_landed for fight in selected)
    takedowns_attempted = sum(fight.takedowns_attempted for fight in selected)
    opponent_takedowns_landed = sum(fight.opponent_takedowns_landed for fight in selected)
    opponent_takedowns_attempted = sum(fight.opponent_takedowns_attempted for fight in selected)
    eligible = [fight for fight in selected if fight.result not in {FightResult.NO_CONTEST, FightResult.OVERTURNED}]
    wins = [fight for fight in eligible if fight.won]
    finishes = [fight for fight in wins if not _is_decision(fight.method)]
    early_seconds = sum(fight.early_seconds for fight in selected)
    late_seconds = sum(fight.late_seconds for fight in selected)
    early_rate = safe_ratio(sum(fight.early_output for fight in selected), early_seconds)
    late_rate = safe_ratio(sum(fight.late_output for fight in selected), late_seconds)

    return RollingMetrics(
        window_type=window,
        fights_count=len(selected),
        rounds_count=sum(fight.rounds_observed for fight in selected),
        minutes_observed=elapsed_seconds / 60.0,
        significant_strikes_landed_per_minute=landed * scale_per_minute,
        significant_strikes_absorbed_per_minute=absorbed * scale_per_minute,
        significant_strike_differential_per_minute=(landed - absorbed) * scale_per_minute,
        significant_strike_accuracy=safe_ratio(landed, attempted),
        significant_strike_defence=1.0 - safe_ratio(absorbed, opponent_attempted) if opponent_attempted else 0.0,
        strike_attempts_per_minute=attempted * scale_per_minute,
        knockdowns_per_15=sum(fight.knockdowns for fight in selected) * scale_per_15,
        knockdowns_absorbed_per_15=sum(fight.knockdowns_absorbed for fight in selected) * scale_per_15,
        takedowns_landed_per_15=takedowns_landed * scale_per_15,
        takedown_attempts_per_15=takedowns_attempted * scale_per_15,
        takedown_accuracy=safe_ratio(takedowns_landed, takedowns_attempted),
        takedown_defence=(
            1.0 - safe_ratio(opponent_takedowns_landed, opponent_takedowns_attempted)
            if opponent_takedowns_attempted
            else 0.0
        ),
        control_seconds_per_15=sum(fight.control_time_seconds for fight in selected) * scale_per_15,
        control_differential_per_15=(
            sum(fight.control_time_seconds - fight.opponent_control_time_seconds for fight in selected) * scale_per_15
        ),
        submission_attempts_per_15=sum(fight.submission_attempts for fight in selected) * scale_per_15,
        win_rate=safe_ratio(len(wins), len(eligible)),
        finish_rate=safe_ratio(len(finishes), len(wins)),
        knockout_rate=safe_ratio(sum(_is_knockout(fight.method) for fight in wins), len(wins)),
        submission_rate=safe_ratio(sum(_is_submission(fight.method) for fight in wins), len(wins)),
        decision_rate=safe_ratio(sum(_is_decision(fight.method) for fight in wins), len(wins)),
        late_round_output_ratio=safe_ratio(late_rate, early_rate),
    )


def _is_decision(method: str | None) -> bool:
    return bool(method and "decision" in method.lower())


def _is_knockout(method: str | None) -> bool:
    return bool(method and ("ko" in method.lower() or "knockout" in method.lower()))


def _is_submission(method: str | None) -> bool:
    return bool(method and "submission" in method.lower())
