from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum
from uuid import UUID


class RatingTrack(StrEnum):
    OVERALL = "overall"
    STRIKING = "striking"
    WRESTLING = "wrestling"
    SUBMISSION = "submission"
    DEFENCE = "defence"
    FIVE_ROUND = "five_round"


class EloResult(StrEnum):
    FIGHTER_A_WIN = "fighter_a_win"
    FIGHTER_B_WIN = "fighter_b_win"
    DRAW = "draw"
    NO_CONTEST = "no_contest"
    OVERTURNED = "overturned"


@dataclass(frozen=True, slots=True)
class EloConfig:
    initial_rating: float = 1500.0
    k_factor: float = 32.0
    method_multiplier: float = 1.0
    dominance_multiplier: float = 1.0
    context_multiplier: float = 1.0

    def __post_init__(self) -> None:
        if self.k_factor < 0:
            raise ValueError("k_factor cannot be negative")
        if min(self.method_multiplier, self.dominance_multiplier, self.context_multiplier) < 0:
            raise ValueError("Elo multipliers cannot be negative")


@dataclass(frozen=True, slots=True)
class EloFight:
    fight_id: UUID
    event_date: date
    fighter_a_id: UUID
    fighter_b_id: UUID
    result: EloResult
    scheduled_rounds: int = 3
    track_results: dict[RatingTrack, float] = field(default_factory=dict)
    method_multiplier: float = 1.0
    dominance_multiplier: float = 1.0
    context_multiplier: float = 1.0


@dataclass(frozen=True, slots=True)
class RatingSnapshot:
    fight_id: UUID
    event_date: date
    fighter_a_id: UUID
    fighter_b_id: UUID
    pre_fight_a: dict[RatingTrack, float]
    pre_fight_b: dict[RatingTrack, float]
    post_fight_a: dict[RatingTrack, float]
    post_fight_b: dict[RatingTrack, float]


def expected_score(rating_a: float, rating_b: float) -> float:
    return 1.0 / (1.0 + 10 ** ((rating_b - rating_a) / 400.0))


def update_rating(
    rating: float,
    opponent_rating: float,
    actual: float,
    *,
    k_factor: float,
    multiplier: float = 1.0,
) -> float:
    if not 0.0 <= actual <= 1.0:
        raise ValueError("actual result must be between 0 and 1")
    return rating + k_factor * multiplier * (actual - expected_score(rating, opponent_rating))


def calculate_elo_history(fights: list[EloFight], config: EloConfig | None = None) -> list[RatingSnapshot]:
    config = config or EloConfig()
    ratings: dict[UUID, dict[RatingTrack, float]] = {}
    history: list[RatingSnapshot] = []
    for fight in sorted(fights, key=lambda item: (item.event_date, str(item.fight_id))):
        ratings.setdefault(fight.fighter_a_id, _initial_tracks(config.initial_rating))
        ratings.setdefault(fight.fighter_b_id, _initial_tracks(config.initial_rating))
        pre_a = ratings[fight.fighter_a_id].copy()
        pre_b = ratings[fight.fighter_b_id].copy()
        post_a = pre_a.copy()
        post_b = pre_b.copy()
        actual_overall = _actual_for_a(fight.result)
        if actual_overall is not None:
            multiplier = (
                config.method_multiplier
                * config.dominance_multiplier
                * config.context_multiplier
                * fight.method_multiplier
                * fight.dominance_multiplier
                * fight.context_multiplier
            )
            for track in RatingTrack:
                if track is RatingTrack.FIVE_ROUND and fight.scheduled_rounds != 5:
                    continue
                actual_a = fight.track_results.get(track, actual_overall)
                post_a[track] = update_rating(
                    pre_a[track], pre_b[track], actual_a, k_factor=config.k_factor, multiplier=multiplier
                )
                post_b[track] = update_rating(
                    pre_b[track], pre_a[track], 1.0 - actual_a, k_factor=config.k_factor, multiplier=multiplier
                )
        ratings[fight.fighter_a_id] = post_a
        ratings[fight.fighter_b_id] = post_b
        history.append(
            RatingSnapshot(
                fight.fight_id,
                fight.event_date,
                fight.fighter_a_id,
                fight.fighter_b_id,
                pre_a,
                pre_b,
                post_a.copy(),
                post_b.copy(),
            )
        )
    return history


def _initial_tracks(initial_rating: float) -> dict[RatingTrack, float]:
    return {track: initial_rating for track in RatingTrack}


def _actual_for_a(result: EloResult) -> float | None:
    if result is EloResult.FIGHTER_A_WIN:
        return 1.0
    if result is EloResult.FIGHTER_B_WIN:
        return 0.0
    if result is EloResult.DRAW:
        return 0.5
    return None
