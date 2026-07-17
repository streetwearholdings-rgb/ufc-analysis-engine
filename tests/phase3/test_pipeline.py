from collections.abc import Generator
from datetime import date, timedelta
from pathlib import Path
from uuid import UUID

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.database.base import Base
from app.database.models.event import Event
from app.database.models.fight import Fight, FightResult
from app.database.models.fight_round_stat import FightRoundStat
from app.database.models.fight_training_record import FightTrainingRecord
from app.database.models.fighter import Fighter
from app.database.models.fighter_feature_snapshot import FighterFeatureSnapshot
from app.evaluation.chronological_split import proportional_chronological_split, walk_forward_splits
from app.evaluation.metrics import evaluate_probabilities
from app.ml.elo_baseline import elo_win_probability
from app.ml.logistic_model import MODEL_FEATURES, train_logistic_model
from app.phase3.historical_snapshots import HistoricalSnapshotService, default_fighter_state
from app.phase3.matchup_features import LeakageDetectionError, state_from_snapshot
from app.phase3.training_dataset import TRAINING_COLUMNS, TrainingDatasetBuilder

A = UUID(int=101)
B = UUID(int=102)
C = UUID(int=103)
START = date(2020, 1, 1)


@pytest.fixture
def session() -> Generator[Session, None, None]:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as db:
        _seed(db)
        yield db


def test_default_state_is_deterministic() -> None:
    first = default_fighter_state()
    second = default_fighter_state()
    assert first.elo_rating == second.elo_rating == 1500
    assert first.fights_completed == first.wins == first.losses == first.draws == 0
    assert first.performance_score == first.striking_score == 50


def test_snapshots_update_wins_losses_draws_no_contests_and_elo(session: Session) -> None:
    result = HistoricalSnapshotService(session).rebuild()
    session.flush()
    snapshots = list(
        session.scalars(
            select(FighterFeatureSnapshot).order_by(
                FighterFeatureSnapshot.snapshot_date, FighterFeatureSnapshot.source_fight_id
            )
        )
    )

    assert result.fights_processed == 4
    assert result.snapshots_written == 8
    a_first = next(item for item in snapshots if item.fighter_id == A and item.source_fight_id == UUID(int=301))
    b_first = next(item for item in snapshots if item.fighter_id == B and item.source_fight_id == UUID(int=301))
    assert a_first.wins == 1 and a_first.elo_rating == pytest.approx(1516)
    assert b_first.losses == 1 and b_first.elo_rating == pytest.approx(1484)
    a_draw = next(item for item in snapshots if item.fighter_id == A and item.source_fight_id == UUID(int=303))
    assert a_draw.draws == 1
    b_nc = next(item for item in snapshots if item.fighter_id == B and item.source_fight_id == UUID(int=304))
    assert b_nc.wins == 0 and b_nc.losses == 1 and b_nc.draws == 1


def test_snapshot_rebuild_is_idempotent_and_ordered(session: Session) -> None:
    service = HistoricalSnapshotService(session)
    service.rebuild()
    first_count = session.scalar(select(func.count()).select_from(FighterFeatureSnapshot))
    service.rebuild()
    second_count = session.scalar(select(func.count()).select_from(FighterFeatureSnapshot))

    assert first_count == second_count == 8
    assert session.scalar(
        select(func.count()).select_from(FighterFeatureSnapshot).where(FighterFeatureSnapshot.fighter_id == A)
    ) == 3


def test_training_records_are_strictly_prefight_and_exclude_invalid_outcomes(session: Session) -> None:
    HistoricalSnapshotService(session).rebuild()
    result = TrainingDatasetBuilder(session).build_training_dataset()

    assert [row["fight_id"] for row in result.rows] == [UUID(int=301), UUID(int=302)]
    first, second = result.rows
    assert first["a_fights_completed"] == first["b_fights_completed"] == 0
    assert second["a_fights_completed"] == 1
    assert second["a_elo_rating"] == pytest.approx(1516)
    assert second["fighter_a_win"] is False
    assert session.scalar(select(func.count()).select_from(FightTrainingRecord)) == 2


def test_dataset_rebuild_is_idempotent_and_mirroring_inverts_features(session: Session) -> None:
    HistoricalSnapshotService(session).rebuild()
    builder = TrainingDatasetBuilder(session)
    original = builder.build_training_dataset()
    repeated = builder.build_training_dataset(include_mirrored_rows=True)

    assert session.scalar(select(func.count()).select_from(FightTrainingRecord)) == 2
    assert len(repeated.rows) == 4
    mirrored = repeated.rows[1]
    assert mirrored["fighter_a_id"] == original.rows[0]["fighter_b_id"]
    original_elo = original.rows[0]["elo_difference"]
    assert isinstance(original_elo, int | float)
    assert mirrored["elo_difference"] == -float(original_elo)
    assert mirrored["fighter_a_win"] is not original.rows[0]["fighter_a_win"]


def test_csv_columns_and_order_are_stable(session: Session, tmp_path: Path) -> None:
    HistoricalSnapshotService(session).rebuild()
    builder = TrainingDatasetBuilder(session)
    rows = builder.build_training_dataset(persist=False).rows
    path = tmp_path / "training.csv"
    builder.export_csv(rows, path)

    assert path.read_text().splitlines()[0].split(",") == list(TRAINING_COLUMNS)
    assert list(rows[0]) == list(TRAINING_COLUMNS)


def test_leakage_guard_rejects_target_snapshot(session: Session) -> None:
    HistoricalSnapshotService(session).rebuild()
    snapshot = session.scalar(
        select(FighterFeatureSnapshot).where(FighterFeatureSnapshot.source_fight_id == UUID(int=302))
    )
    assert snapshot is not None
    with pytest.raises(LeakageDetectionError, match="not strictly before"):
        state_from_snapshot(snapshot, target_date=START + timedelta(days=10))


def test_model_pipeline_is_chronological_deterministic_and_train_only() -> None:
    rows = [_model_row(index) for index in range(20)]
    split = proportional_chronological_split(rows)
    assert max(row["event_date"] for row in split.train) < min(row["event_date"] for row in split.validation)
    assert max(row["event_date"] for row in split.validation) < min(row["event_date"] for row in split.test)
    first = train_logistic_model(split.train, split.validation)
    second = train_logistic_model(split.train, split.validation)
    probabilities = first.predict_proba(split.test)

    assert all(0 <= value <= 1 for value in probabilities)
    assert probabilities == pytest.approx(second.predict_proba(split.test))
    preprocessing = first.pipeline.named_steps["preprocessing"]
    statistics = preprocessing.named_transformers_["numeric"].named_steps["imputer"].statistics_
    assert statistics[MODEL_FEATURES.index("age_difference")] < 100
    assert walk_forward_splits(rows, minimum_train_size=10, validation_size=3, test_size=2)


def test_evaluation_metrics_and_elo_baseline() -> None:
    metrics = evaluate_probabilities([0, 1, 0, 1], [0.1, 0.8, 0.3, 0.9]).as_dict()
    assert set(metrics) == {
        "accuracy",
        "log_loss",
        "brier_score",
        "roc_auc",
        "expected_calibration_error",
        "sample_size",
    }
    assert elo_win_probability(0) == 0.5
    assert evaluate_probabilities([1], [0.7]).roc_auc is None
    with pytest.raises(ValueError, match="same length"):
        evaluate_probabilities([0, 1], [0.5])


def _seed(session: Session) -> None:
    session.add_all(
        [
            Fighter(id=A, external_id="a", first_name="A", last_name="One", date_of_birth=date(1990, 1, 1)),
            Fighter(id=B, external_id="b", first_name="B", last_name="Two", height_cm=180, reach_cm=185),
            Fighter(id=C, external_id="c", first_name="C", last_name="Three", height_cm=175, reach_cm=178),
        ]
    )
    session.flush()
    _fight(session, 301, 201, START, A, B, A, FightResult.FIGHTER_A_WIN)
    _fight(session, 302, 202, START + timedelta(days=10), A, C, C, FightResult.FIGHTER_B_WIN)
    _fight(session, 303, 203, START + timedelta(days=20), A, B, None, FightResult.DRAW)
    _fight(session, 304, 204, START + timedelta(days=30), B, C, None, FightResult.NO_CONTEST)
    session.commit()


def _fight(
    session: Session,
    fight_number: int,
    event_number: int,
    event_date: date,
    fighter_a: UUID,
    fighter_b: UUID,
    winner: UUID | None,
    result: FightResult,
) -> None:
    event_id, fight_id = UUID(int=event_number), UUID(int=fight_number)
    session.add(Event(id=event_id, external_id=f"e-{event_number}", name="Fixture", event_date=event_date))
    session.flush()
    loser = fighter_b if winner == fighter_a else fighter_a if winner == fighter_b else None
    session.add(
        Fight(
            id=fight_id,
            external_id=f"f-{fight_number}",
            event_id=event_id,
            fighter_a_id=fighter_a,
            fighter_b_id=fighter_b,
            winner_id=winner,
            loser_id=loser,
            weight_class="Lightweight",
            scheduled_rounds=3,
            completed_rounds=1,
            result=result,
            method="Unanimous Decision",
        )
    )
    session.flush()
    session.add_all([_stat(fight_id, fighter_a, fighter_b, 20, 15), _stat(fight_id, fighter_b, fighter_a, 15, 20)])
    session.flush()


def _stat(fight_id: UUID, fighter_id: UUID, opponent_id: UUID, landed: int, absorbed: int) -> FightRoundStat:
    return FightRoundStat(
        fight_id=fight_id,
        fighter_id=fighter_id,
        opponent_id=opponent_id,
        round_number=1,
        round_duration_seconds=300,
        significant_strikes_landed=landed,
        significant_strikes_attempted=40,
        total_strikes_landed=landed,
        total_strikes_attempted=40,
        takedowns_landed=1 if landed > absorbed else 0,
        takedowns_attempted=2,
        control_time_seconds=30,
    )


def _model_row(index: int) -> dict[str, object]:
    row: dict[str, object] = {
        "fight_id": UUID(int=1000 + index),
        "event_date": START + timedelta(days=index),
        "fighter_a_win": index % 2 == 0,
    }
    for feature_index, feature in enumerate(MODEL_FEATURES):
        row[feature] = float(index + feature_index) if feature != "age_difference" else float(index)
    if index >= 12:
        row["age_difference"] = 1000.0
    return row
