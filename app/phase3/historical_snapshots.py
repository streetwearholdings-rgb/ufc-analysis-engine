from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import date
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.calculations.elo import update_rating
from app.database.models.event import Event
from app.database.models.fight import Fight, FightResult
from app.database.models.fight_round_stat import FightRoundStat
from app.database.models.fighter_feature_snapshot import FighterFeatureSnapshot


@dataclass(slots=True)
class HistoricalFighterState:
    fights_completed: int = 0
    wins: int = 0
    losses: int = 0
    draws: int = 0
    elo_rating: float = 1500.0
    striking_score: float = 50.0
    grappling_score: float = 50.0
    defence_score: float = 50.0
    performance_score: float = 50.0
    recent_form_score: float = 50.0
    strength_of_schedule: float = 1500.0
    finish_rate: float = 0.0
    average_fight_time: float = 0.0
    days_since_last_fight: int | None = None
    data_quality_score: float = 0.0
    last_fight_date: date | None = None
    finishes: int = 0
    total_fight_seconds: int = 0
    opponent_rating_total: float = 0.0
    striking_total: float = 0.0
    grappling_total: float = 0.0
    defence_total: float = 0.0
    performance_total: float = 0.0
    quality_total: float = 0.0
    recent_performances: deque[float] = field(default_factory=lambda: deque(maxlen=3))

    def copy(self) -> "HistoricalFighterState":
        result = HistoricalFighterState()
        for name in self.__dataclass_fields__:
            value = getattr(self, name)
            setattr(result, name, deque(value, maxlen=3) if name == "recent_performances" else value)
        return result


@dataclass(frozen=True, slots=True)
class SnapshotBuildResult:
    fights_processed: int
    snapshots_written: int


def default_fighter_state(initial_rating: float = 1500.0) -> HistoricalFighterState:
    return HistoricalFighterState(elo_rating=initial_rating, strength_of_schedule=initial_rating)


class HistoricalSnapshotService:
    """Reconstruct fighter state chronologically without reading derived future data."""

    def __init__(self, session: Session, *, initial_rating: float = 1500.0, k_factor: float = 32.0) -> None:
        self.session = session
        self.initial_rating = initial_rating
        self.k_factor = k_factor

    def rebuild(self, *, reset: bool = False) -> SnapshotBuildResult:
        if reset:
            self.session.execute(delete(FighterFeatureSnapshot))
        fights = list(
            self.session.execute(
                select(Fight, Event.event_date)
                .join(Event, Event.id == Fight.event_id)
                .order_by(Event.event_date, Fight.id)
            )
        )
        stats = self._load_stats([row[0].id for row in fights])
        existing = {
            (snapshot.fighter_id, snapshot.source_fight_id): snapshot
            for snapshot in self.session.scalars(select(FighterFeatureSnapshot))
        }
        states: dict[UUID, HistoricalFighterState] = {}
        written = 0
        for row in fights:
            fight, event_date = row[0], row[1]
            a_state = states.setdefault(fight.fighter_a_id, default_fighter_state(self.initial_rating))
            b_state = states.setdefault(fight.fighter_b_id, default_fighter_state(self.initial_rating))
            pre_a, pre_b = a_state.copy(), b_state.copy()
            self._apply_fight(
                a_state, b_state, fight, event_date, stats.get(fight.id, []), fight.fighter_a_id, pre_b=pre_b
            )
            self._apply_fight(
                b_state,
                a_state,
                fight,
                event_date,
                stats.get(fight.id, []),
                fight.fighter_b_id,
                pre_b=pre_a,
            )
            self._upsert(existing, fight.fighter_a_id, fight.id, event_date, a_state)
            self._upsert(existing, fight.fighter_b_id, fight.id, event_date, b_state)
            written += 2
        self.session.flush()
        return SnapshotBuildResult(len(fights), written)

    def _apply_fight(
        self,
        state: HistoricalFighterState,
        opponent_state: HistoricalFighterState,
        fight: Fight,
        event_date: date,
        rows: list[FightRoundStat],
        fighter_id: UUID,
        *,
        pre_b: HistoricalFighterState | None = None,
    ) -> None:
        opponent_pre_rating = pre_b.elo_rating if pre_b else opponent_state.elo_rating
        own = [item for item in rows if item.fighter_id == fighter_id]
        opponent = [item for item in rows if item.fighter_id != fighter_id]
        elapsed = sum(item.round_duration_seconds for item in own)
        landed = sum(item.significant_strikes_landed for item in own)
        attempted = sum(item.significant_strikes_attempted for item in own)
        absorbed = sum(item.significant_strikes_landed for item in opponent)
        opponent_attempted = sum(item.significant_strikes_attempted for item in opponent)
        takedowns = sum(item.takedowns_landed for item in own)
        submissions = sum(item.submission_attempts for item in own)
        control = sum(item.control_time_seconds for item in own)
        striking = _clamp(50 + (landed - absorbed) * 1.5 + _ratio(landed, attempted) * 20)
        grappling = _clamp(40 + takedowns * 8 + submissions * 10 + control / 30)
        defence = _clamp((1 - _ratio(absorbed, opponent_attempted)) * 100 if opponent_attempted else 50)
        performance = 0.4 * striking + 0.3 * grappling + 0.3 * defence
        expected_rows = max(fight.completed_rounds, 1)
        quality = min(1.0, len(own) / expected_rows) if elapsed else 0.0
        previous_date = state.last_fight_date
        state.days_since_last_fight = (event_date - previous_date).days if previous_date else None
        state.last_fight_date = event_date
        state.fights_completed += 1
        state.total_fight_seconds += elapsed
        state.average_fight_time = state.total_fight_seconds / state.fights_completed
        state.opponent_rating_total += opponent_pre_rating
        state.striking_total += striking
        state.grappling_total += grappling
        state.defence_total += defence
        state.performance_total += performance
        state.quality_total += quality
        state.striking_score = state.striking_total / state.fights_completed
        state.grappling_score = state.grappling_total / state.fights_completed
        state.defence_score = state.defence_total / state.fights_completed
        state.performance_score = state.performance_total / state.fights_completed
        state.data_quality_score = state.quality_total / state.fights_completed
        state.recent_performances.append(performance)
        state.recent_form_score = sum(state.recent_performances) / len(state.recent_performances)
        state.strength_of_schedule = state.opponent_rating_total / state.fights_completed
        actual = _actual_result(fight, fighter_id)
        if actual is not None:
            state.elo_rating = update_rating(
                state.elo_rating, opponent_pre_rating, actual, k_factor=self.k_factor
            )
        if fight.result == FightResult.DRAW:
            state.draws += 1
        elif fight.winner_id == fighter_id:
            state.wins += 1
            if fight.method and "decision" not in fight.method.lower():
                state.finishes += 1
        elif fight.loser_id == fighter_id:
            state.losses += 1
        state.finish_rate = state.finishes / state.wins if state.wins else 0.0

    def _upsert(
        self,
        existing: dict[tuple[UUID, UUID], FighterFeatureSnapshot],
        fighter_id: UUID,
        fight_id: UUID,
        snapshot_date: date,
        state: HistoricalFighterState,
    ) -> None:
        row = existing.get((fighter_id, fight_id))
        values = _snapshot_values(state)
        if row is None:
            row = FighterFeatureSnapshot(
                fighter_id=fighter_id,
                source_fight_id=fight_id,
                snapshot_date=snapshot_date,
                **values,
            )
            self.session.add(row)
            existing[(fighter_id, fight_id)] = row
            return
        row.snapshot_date = snapshot_date
        for name, value in values.items():
            setattr(row, name, value)

    def _load_stats(self, fight_ids: list[UUID]) -> dict[UUID, list[FightRoundStat]]:
        grouped: dict[UUID, list[FightRoundStat]] = defaultdict(list)
        if fight_ids:
            for row in self.session.scalars(select(FightRoundStat).where(FightRoundStat.fight_id.in_(fight_ids))):
                grouped[row.fight_id].append(row)
        return dict(grouped)


def _snapshot_values(state: HistoricalFighterState) -> dict[str, int | float | None]:
    return {
        "fights_completed": state.fights_completed,
        "wins": state.wins,
        "losses": state.losses,
        "draws": state.draws,
        "elo_rating": state.elo_rating,
        "striking_score": state.striking_score,
        "grappling_score": state.grappling_score,
        "defence_score": state.defence_score,
        "performance_score": state.performance_score,
        "recent_form_score": state.recent_form_score,
        "strength_of_schedule": state.strength_of_schedule,
        "finish_rate": state.finish_rate,
        "average_fight_time": state.average_fight_time,
        "days_since_last_fight": state.days_since_last_fight,
        "data_quality_score": state.data_quality_score,
    }


def _actual_result(fight: Fight, fighter_id: UUID) -> float | None:
    if fight.result in {FightResult.NO_CONTEST, FightResult.OVERTURNED}:
        return None
    if fight.result == FightResult.DRAW:
        return 0.5
    return 1.0 if fight.winner_id == fighter_id else 0.0


def _ratio(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else 0.0


def _clamp(value: float) -> float:
    return min(100.0, max(0.0, value))
