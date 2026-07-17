from dataclasses import dataclass
from datetime import date

from app.database.models.fight import Fight
from app.database.models.fighter import Fighter
from app.database.models.fighter_feature_snapshot import FighterFeatureSnapshot
from app.phase3.historical_snapshots import HistoricalFighterState, default_fighter_state


class LeakageDetectionError(ValueError):
    """Raised when a target or future snapshot is selected as a model input."""


@dataclass(frozen=True, slots=True)
class PrefightState:
    fights_completed: int
    elo_rating: float
    striking_score: float
    grappling_score: float
    defence_score: float
    performance_score: float
    recent_form_score: float
    strength_of_schedule: float
    finish_rate: float
    data_quality_score: float
    snapshot_date: date | None


def state_from_snapshot(
    snapshot: FighterFeatureSnapshot | None,
    *,
    target_date: date,
    initial_rating: float = 1500.0,
) -> PrefightState:
    if snapshot is None:
        return _from_default(default_fighter_state(initial_rating))
    if snapshot.snapshot_date >= target_date:
        raise LeakageDetectionError(
            f"Snapshot {snapshot.id} dated {snapshot.snapshot_date} is not strictly before target date {target_date}"
        )
    return PrefightState(
        snapshot.fights_completed,
        snapshot.elo_rating,
        snapshot.striking_score,
        snapshot.grappling_score,
        snapshot.defence_score,
        snapshot.performance_score,
        snapshot.recent_form_score,
        snapshot.strength_of_schedule,
        snapshot.finish_rate,
        snapshot.data_quality_score,
        snapshot.snapshot_date,
    )


def construct_training_values(
    fight: Fight,
    event_date: date,
    fighter_a: Fighter,
    fighter_b: Fighter,
    snapshot_a: FighterFeatureSnapshot | None,
    snapshot_b: FighterFeatureSnapshot | None,
    *,
    initial_rating: float = 1500.0,
) -> dict[str, object]:
    a = state_from_snapshot(snapshot_a, target_date=event_date, initial_rating=initial_rating)
    b = state_from_snapshot(snapshot_b, target_date=event_date, initial_rating=initial_rating)
    a_age = _age(fighter_a.date_of_birth, event_date)
    b_age = _age(fighter_b.date_of_birth, event_date)
    a_layoff = (event_date - a.snapshot_date).days if a.snapshot_date else None
    b_layoff = (event_date - b.snapshot_date).days if b.snapshot_date else None
    return {
        "fight_id": fight.id,
        "event_date": event_date,
        "fighter_a_id": fighter_a.id,
        "fighter_b_id": fighter_b.id,
        "weight_class": fight.weight_class,
        "scheduled_rounds": fight.scheduled_rounds,
        "a_fights_completed": a.fights_completed,
        "b_fights_completed": b.fights_completed,
        "experience_difference": float(a.fights_completed - b.fights_completed),
        "a_age": a_age,
        "b_age": b_age,
        "age_difference": _difference(a_age, b_age),
        "age_missing": a_age is None or b_age is None,
        "a_height": fighter_a.height_cm,
        "b_height": fighter_b.height_cm,
        "height_difference": _difference(fighter_a.height_cm, fighter_b.height_cm),
        "height_missing": fighter_a.height_cm is None or fighter_b.height_cm is None,
        "a_reach": fighter_a.reach_cm,
        "b_reach": fighter_b.reach_cm,
        "reach_difference": _difference(fighter_a.reach_cm, fighter_b.reach_cm),
        "reach_missing": fighter_a.reach_cm is None or fighter_b.reach_cm is None,
        "a_elo_rating": a.elo_rating,
        "b_elo_rating": b.elo_rating,
        "elo_difference": a.elo_rating - b.elo_rating,
        "a_striking_score": a.striking_score,
        "b_striking_score": b.striking_score,
        "striking_difference": a.striking_score - b.striking_score,
        "a_grappling_score": a.grappling_score,
        "b_grappling_score": b.grappling_score,
        "grappling_difference": a.grappling_score - b.grappling_score,
        "a_defence_score": a.defence_score,
        "b_defence_score": b.defence_score,
        "defence_difference": a.defence_score - b.defence_score,
        "a_performance_score": a.performance_score,
        "b_performance_score": b.performance_score,
        "performance_difference": a.performance_score - b.performance_score,
        "a_recent_form_score": a.recent_form_score,
        "b_recent_form_score": b.recent_form_score,
        "recent_form_difference": a.recent_form_score - b.recent_form_score,
        "a_strength_of_schedule": a.strength_of_schedule,
        "b_strength_of_schedule": b.strength_of_schedule,
        "strength_of_schedule_difference": a.strength_of_schedule - b.strength_of_schedule,
        "a_finish_rate": a.finish_rate,
        "b_finish_rate": b.finish_rate,
        "finish_rate_difference": a.finish_rate - b.finish_rate,
        "a_days_since_last_fight": a_layoff,
        "b_days_since_last_fight": b_layoff,
        "layoff_difference": _difference(a_layoff, b_layoff),
        "layoff_missing": a_layoff is None or b_layoff is None,
        "a_data_quality_score": a.data_quality_score,
        "b_data_quality_score": b.data_quality_score,
        "minimum_data_quality": min(a.data_quality_score, b.data_quality_score),
        "fighter_a_win": fight.winner_id == fighter_a.id,
    }


def _from_default(state: HistoricalFighterState) -> PrefightState:
    return PrefightState(
        state.fights_completed,
        state.elo_rating,
        state.striking_score,
        state.grappling_score,
        state.defence_score,
        state.performance_score,
        state.recent_form_score,
        state.strength_of_schedule,
        state.finish_rate,
        state.data_quality_score,
        None,
    )


def _age(birth_date: date | None, event_date: date) -> float | None:
    return (event_date - birth_date).days / 365.2425 if birth_date else None


def _difference(a: float | int | None, b: float | int | None) -> float | None:
    return float(a - b) if a is not None and b is not None else None
