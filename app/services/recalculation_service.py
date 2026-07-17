import logging
from datetime import date
from time import monotonic
from uuid import UUID

from sqlalchemy.orm import Session

from app.calculations.rolling_averages import RollingMetrics, RollingWindow, calculate_rolling_metrics
from app.config import get_settings
from app.database.models.fighter_rolling_stat import FighterRollingStat
from app.repositories.fighters import FighterRepository
from app.repositories.fights import FightFilters
from app.repositories.stats import StatsRepository
from app.utils.logging import log_event

logger = logging.getLogger(__name__)


class RecalculationService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.stats = StatsRepository(session)

    def recalculate_fighter(self, fighter_id: UUID, calculation_date: date | None = None) -> list[str]:
        started = monotonic()
        calculation_date = calculation_date or date.today()
        fighter = FighterRepository(self.session).get(fighter_id)
        if fighter is None:
            raise LookupError("Fighter not found")
        weight_class = fighter.current_weight_class or "Unknown"
        lines = self.stats.fight_stat_lines(
            fighter_id,
            as_of=calculation_date,
            filters=FightFilters(weight_class=fighter.current_weight_class),
        )
        log_event(
            logger,
            "calculation_started",
            fighter_id=fighter_id,
            fight_count=len(lines),
            model_version=get_settings().model_version,
        )
        rebuilt: list[str] = []
        for window in (RollingWindow.LAST_3, RollingWindow.LAST_5):
            metrics = calculate_rolling_metrics(lines, window)
            self.stats.replace_rolling(_rolling_row(fighter_id, calculation_date, weight_class, metrics))
            rebuilt.append(window.value)
        self.session.commit()
        log_event(
            logger,
            "calculation_completed",
            fighter_id=fighter_id,
            windows=rebuilt,
            duration_seconds=round(monotonic() - started, 6),
            model_version=get_settings().model_version,
        )
        return rebuilt

    def rebuild_all(self, calculation_date: date | None = None) -> tuple[int, int]:
        processed = failed = 0
        for fighter in FighterRepository(self.session).active():
            try:
                self.recalculate_fighter(fighter.id, calculation_date)
                processed += 1
            except Exception:
                self.session.rollback()
                failed += 1
                logger.exception("fighter_recalculation_failed", extra={"fighter_id": str(fighter.id)})
        return processed, failed


def _rolling_row(
    fighter_id: UUID, calculation_date: date, weight_class: str, metrics: RollingMetrics
) -> FighterRollingStat:
    return FighterRollingStat(
        fighter_id=fighter_id,
        calculation_date=calculation_date,
        window_type=metrics.window_type.value,
        weight_class=weight_class,
        fights_count=metrics.fights_count,
        rounds_count=metrics.rounds_count,
        minutes_observed=metrics.minutes_observed,
        significant_strikes_landed_per_minute=metrics.significant_strikes_landed_per_minute,
        significant_strikes_absorbed_per_minute=metrics.significant_strikes_absorbed_per_minute,
        significant_strike_differential_per_minute=metrics.significant_strike_differential_per_minute,
        significant_strike_accuracy=metrics.significant_strike_accuracy,
        significant_strike_defence=metrics.significant_strike_defence,
        strike_attempts_per_minute=metrics.strike_attempts_per_minute,
        knockdowns_per_15=metrics.knockdowns_per_15,
        knockdowns_absorbed_per_15=metrics.knockdowns_absorbed_per_15,
        takedowns_landed_per_15=metrics.takedowns_landed_per_15,
        takedown_attempts_per_15=metrics.takedown_attempts_per_15,
        takedown_accuracy=metrics.takedown_accuracy,
        takedown_defence=metrics.takedown_defence,
        control_seconds_per_15=metrics.control_seconds_per_15,
        control_differential_per_15=metrics.control_differential_per_15,
        submission_attempts_per_15=metrics.submission_attempts_per_15,
        win_rate=metrics.win_rate,
        finish_rate=metrics.finish_rate,
        knockout_rate=metrics.knockout_rate,
        submission_rate=metrics.submission_rate,
        decision_rate=metrics.decision_rate,
        round_win_rate=0.0,
        late_round_output_ratio=metrics.late_round_output_ratio,
    )
