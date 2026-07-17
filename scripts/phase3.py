import argparse
import json
import logging
from datetime import date
from pathlib import Path
from typing import Any

import joblib

from app.config import get_settings
from app.database.session import SessionLocal
from app.evaluation.chronological_split import proportional_chronological_split
from app.evaluation.metrics import evaluate_probabilities
from app.ml.elo_baseline import predict_elo_probabilities
from app.ml.logistic_model import LogisticModelBundle, train_logistic_model
from app.phase3.historical_snapshots import HistoricalSnapshotService
from app.phase3.training_dataset import TrainingDatasetBuilder

logger = logging.getLogger(__name__)


def main() -> None:
    parser = _parser()
    args = parser.parse_args()
    logging.basicConfig(level=getattr(logging, get_settings().log_level.upper(), logging.INFO))
    if args.command == "rebuild-snapshots":
        _rebuild_snapshots(args)
    elif args.command == "build-training-dataset":
        _build_dataset(args)
    elif args.command == "train-baseline":
        _train(args)
    elif args.command == "evaluate":
        _evaluate(args)
    else:
        parser.error("a Phase 3 command is required")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Phase 3 leakage-safe training pipeline")
    commands = parser.add_subparsers(dest="command")
    snapshots = commands.add_parser("rebuild-snapshots")
    snapshots.add_argument("--reset", action="store_true", help="Explicitly delete existing snapshots first")
    dataset = commands.add_parser("build-training-dataset")
    _dataset_arguments(dataset)
    dataset.add_argument("--output-csv", type=Path)
    dataset.add_argument("--no-persist", action="store_true")
    dataset.add_argument("--reset", action="store_true", help="Explicitly delete existing training records first")
    train = commands.add_parser("train-baseline")
    _dataset_arguments(train)
    train.add_argument("--model-output", type=Path, default=Path("artifacts/phase3_logistic.joblib"))
    evaluate = commands.add_parser("evaluate")
    _dataset_arguments(evaluate)
    evaluate.add_argument("--model", type=Path, default=Path("artifacts/phase3_logistic.joblib"))
    return parser


def _dataset_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--start-date", type=date.fromisoformat)
    parser.add_argument("--end-date", type=date.fromisoformat)
    parser.add_argument("--weight-class", action="append")
    parser.add_argument("--min-data-quality", type=float)
    parser.add_argument("--include-mirrored-rows", action="store_true")


def _rebuild_snapshots(args: argparse.Namespace) -> None:
    with SessionLocal.begin() as session:
        result = HistoricalSnapshotService(session).rebuild(reset=args.reset)
    _log("phase3_snapshots_rebuilt", fights=result.fights_processed, snapshots=result.snapshots_written)


def _build_dataset(args: argparse.Namespace) -> None:
    with SessionLocal.begin() as session:
        builder = TrainingDatasetBuilder(session)
        result = builder.build_training_dataset(
            **_dataset_options(args), persist=not args.no_persist, reset=args.reset
        )
        if args.output_csv:
            builder.export_csv(result.rows, args.output_csv)
    _log("phase3_dataset_built", rows=len(result.rows), persisted=result.persisted, csv=args.output_csv)


def _train(args: argparse.Namespace) -> None:
    rows = _load_rows(args)
    split = proportional_chronological_split(rows)
    model = train_logistic_model(split.train, split.validation)
    model.save(args.model_output)
    logistic = evaluate_probabilities(
        [int(bool(row["fighter_a_win"])) for row in split.test], model.predict_proba(split.test)
    )
    elo = evaluate_probabilities(
        [int(bool(row["fighter_a_win"])) for row in split.test], predict_elo_probabilities(split.test)
    )
    _log("phase3_baseline_trained", model=args.model_output, logistic=logistic.as_dict(), elo=elo.as_dict())


def _evaluate(args: argparse.Namespace) -> None:
    model = joblib.load(args.model)
    if not isinstance(model, LogisticModelBundle):
        raise TypeError("model artifact is not a Phase 3 logistic bundle")
    split = proportional_chronological_split(_load_rows(args))
    metrics = evaluate_probabilities(
        [int(bool(row["fighter_a_win"])) for row in split.test], model.predict_proba(split.test)
    )
    _log("phase3_model_evaluated", model=args.model, metrics=metrics.as_dict())


def _load_rows(args: argparse.Namespace) -> list[dict[str, Any]]:
    with SessionLocal() as session:
        result = TrainingDatasetBuilder(session).build_training_dataset(
            **_dataset_options(args), persist=False
        )
    return result.rows


def _dataset_options(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "start_date": args.start_date,
        "end_date": args.end_date,
        "weight_classes": set(args.weight_class) if args.weight_class else None,
        "min_data_quality": args.min_data_quality,
        "include_mirrored_rows": args.include_mirrored_rows,
    }


def _log(event: str, **fields: Any) -> None:
    logger.info(json.dumps({"event": event, **fields}, default=str, sort_keys=True))


if __name__ == "__main__":
    main()
