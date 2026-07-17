from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

MODEL_FEATURES = (
    "elo_difference",
    "performance_difference",
    "striking_difference",
    "grappling_difference",
    "defence_difference",
    "recent_form_difference",
    "strength_of_schedule_difference",
    "age_difference",
    "reach_difference",
    "experience_difference",
    "layoff_difference",
)


@dataclass(slots=True)
class LogisticModelBundle:
    pipeline: Pipeline
    calibrator: LogisticRegression | None = None

    def predict_proba(self, rows: list[dict[str, Any]]) -> np.ndarray:
        base = self.pipeline.predict_proba(_matrix(rows))[:, 1]
        if self.calibrator is None:
            return np.asarray(base, dtype=float)
        return np.asarray(self.calibrator.predict_proba(base.reshape(-1, 1))[:, 1], dtype=float)

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self, path)


def train_logistic_model(
    train_rows: list[dict[str, Any]], validation_rows: list[dict[str, Any]] | None = None
) -> LogisticModelBundle:
    if not train_rows:
        raise ValueError("training rows cannot be empty")
    target = np.asarray([int(bool(row["fighter_a_win"])) for row in train_rows])
    if len(np.unique(target)) < 2:
        raise ValueError("training requires both outcome classes")
    preprocessing = ColumnTransformer(
        [
            (
                "numeric",
                Pipeline([("imputer", SimpleImputer(strategy="median")), ("scale", StandardScaler())]),
                list(range(len(MODEL_FEATURES))),
            )
        ]
    )
    pipeline = Pipeline(
        [
            ("preprocessing", preprocessing),
            ("classifier", LogisticRegression(random_state=42, max_iter=1000)),
        ]
    )
    pipeline.fit(_matrix(train_rows), target)
    bundle = LogisticModelBundle(pipeline)
    if validation_rows:
        validation_target = np.asarray([int(bool(row["fighter_a_win"])) for row in validation_rows])
        if len(np.unique(validation_target)) > 1:
            base_probabilities = pipeline.predict_proba(_matrix(validation_rows))[:, 1]
            calibrator = LogisticRegression(random_state=42, max_iter=1000)
            calibrator.fit(base_probabilities.reshape(-1, 1), validation_target)
            bundle.calibrator = calibrator
    return bundle


def _matrix(rows: list[dict[str, Any]]) -> np.ndarray:
    return np.asarray([[row.get(feature) for feature in MODEL_FEATURES] for row in rows], dtype=object)
