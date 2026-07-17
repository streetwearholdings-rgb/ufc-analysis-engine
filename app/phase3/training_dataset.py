import csv
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.database.models.event import Event
from app.database.models.fight import Fight, FightResult
from app.database.models.fight_training_record import FightTrainingRecord
from app.database.models.fighter import Fighter
from app.database.models.fighter_feature_snapshot import FighterFeatureSnapshot
from app.phase3.matchup_features import construct_training_values

DIFFERENCE_COLUMNS = (
    "experience_difference",
    "age_difference",
    "height_difference",
    "reach_difference",
    "elo_difference",
    "striking_difference",
    "grappling_difference",
    "defence_difference",
    "performance_difference",
    "recent_form_difference",
    "strength_of_schedule_difference",
    "finish_rate_difference",
    "layoff_difference",
)
PAIR_COLUMNS = (
    ("a_fights_completed", "b_fights_completed"),
    ("a_age", "b_age"),
    ("a_height", "b_height"),
    ("a_reach", "b_reach"),
    ("a_elo_rating", "b_elo_rating"),
    ("a_striking_score", "b_striking_score"),
    ("a_grappling_score", "b_grappling_score"),
    ("a_defence_score", "b_defence_score"),
    ("a_performance_score", "b_performance_score"),
    ("a_recent_form_score", "b_recent_form_score"),
    ("a_strength_of_schedule", "b_strength_of_schedule"),
    ("a_finish_rate", "b_finish_rate"),
    ("a_days_since_last_fight", "b_days_since_last_fight"),
    ("a_data_quality_score", "b_data_quality_score"),
)
TRAINING_COLUMNS = tuple(
    column.name
    for column in FightTrainingRecord.__table__.columns
    if column.name not in {"id", "created_at", "updated_at"}
)


@dataclass(frozen=True, slots=True)
class DatasetBuildResult:
    rows: list[dict[str, object]]
    persisted: int


class TrainingDatasetBuilder:
    def __init__(self, session: Session, *, initial_rating: float = 1500.0) -> None:
        self.session = session
        self.initial_rating = initial_rating

    def build_training_dataset(
        self,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
        weight_classes: set[str] | None = None,
        min_data_quality: float | None = None,
        include_mirrored_rows: bool = False,
        persist: bool = True,
        reset: bool = False,
    ) -> DatasetBuildResult:
        if reset and persist:
            self.session.execute(delete(FightTrainingRecord))
        fighters = {fighter.id: fighter for fighter in self.session.scalars(select(Fighter))}
        snapshots = self._snapshot_index()
        statement = select(Fight, Event.event_date).join(Event, Event.id == Fight.event_id)
        if start_date:
            statement = statement.where(Event.event_date >= start_date)
        if end_date:
            statement = statement.where(Event.event_date <= end_date)
        if weight_classes:
            statement = statement.where(Fight.weight_class.in_(weight_classes))
        statement = statement.where(
            Fight.result.notin_([FightResult.DRAW, FightResult.NO_CONTEST, FightResult.OVERTURNED])
        ).order_by(Event.event_date, Fight.id)
        output: list[dict[str, object]] = []
        persisted = 0
        existing_records = {
            record.fight_id: record for record in self.session.scalars(select(FightTrainingRecord))
        } if persist else {}
        for fight, event_date in self.session.execute(statement):
            if fight.winner_id not in {fight.fighter_a_id, fight.fighter_b_id}:
                continue
            values = construct_training_values(
                fight,
                event_date,
                fighters[fight.fighter_a_id],
                fighters[fight.fighter_b_id],
                _latest_before(snapshots.get(fight.fighter_a_id, []), event_date),
                _latest_before(snapshots.get(fight.fighter_b_id, []), event_date),
                initial_rating=self.initial_rating,
            )
            if min_data_quality is not None and numeric_value(
                values["minimum_data_quality"], field="minimum_data_quality"
            ) < min_data_quality:
                continue
            ordered = {name: values[name] for name in TRAINING_COLUMNS}
            output.append(ordered)
            if persist:
                self._upsert(existing_records, ordered)
                persisted += 1
            if include_mirrored_rows:
                output.append(mirror_training_row(ordered))
        self.session.flush()
        return DatasetBuildResult(output, persisted)

    def export_csv(self, rows: list[dict[str, object]], output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(TRAINING_COLUMNS))
            writer.writeheader()
            writer.writerows(rows)

    def _snapshot_index(self) -> dict[UUID, list[FighterFeatureSnapshot]]:
        result: dict[UUID, list[FighterFeatureSnapshot]] = {}
        for snapshot in self.session.scalars(
            select(FighterFeatureSnapshot).order_by(
                FighterFeatureSnapshot.fighter_id,
                FighterFeatureSnapshot.snapshot_date,
                FighterFeatureSnapshot.source_fight_id,
            )
        ):
            result.setdefault(snapshot.fighter_id, []).append(snapshot)
        return result

    def _upsert(
        self, existing_records: dict[UUID, FightTrainingRecord], values: dict[str, object]
    ) -> None:
        fight_id = values["fight_id"]
        if not isinstance(fight_id, UUID):
            raise TypeError("fight_id must be a UUID")
        row = existing_records.get(fight_id)
        if row is None:
            row = FightTrainingRecord(**values)
            self.session.add(row)
            existing_records[fight_id] = row
            return
        for name, value in values.items():
            if name != "fight_id":
                setattr(row, name, value)


def mirror_training_row(row: dict[str, object]) -> dict[str, object]:
    mirrored = row.copy()
    mirrored["fighter_a_id"], mirrored["fighter_b_id"] = row["fighter_b_id"], row["fighter_a_id"]
    for a_name, b_name in PAIR_COLUMNS:
        mirrored[a_name], mirrored[b_name] = row[b_name], row[a_name]
    for name in DIFFERENCE_COLUMNS:
        value = row[name]
        mirrored[name] = -numeric_value(value, field=name) if value is not None else None
    mirrored["fighter_a_win"] = not bool(row["fighter_a_win"])
    return {name: mirrored[name] for name in TRAINING_COLUMNS}


def _latest_before(
    snapshots: list[FighterFeatureSnapshot], target_date: date
) -> FighterFeatureSnapshot | None:
    eligible = [snapshot for snapshot in snapshots if snapshot.snapshot_date < target_date]
    return eligible[-1] if eligible else None


def numeric_value(value: object, *, field: str) -> float:
    if not isinstance(value, int | float):
        raise TypeError(f"{field} must be numeric")
    return float(value)
