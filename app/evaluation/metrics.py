from dataclasses import asdict, dataclass

import numpy as np
from sklearn.metrics import accuracy_score, brier_score_loss, log_loss, roc_auc_score


@dataclass(frozen=True, slots=True)
class EvaluationMetrics:
    accuracy: float
    log_loss: float
    brier_score: float
    roc_auc: float | None
    expected_calibration_error: float
    sample_size: int

    def as_dict(self) -> dict[str, float | int | None]:
        return asdict(self)


def evaluate_probabilities(
    targets: list[int] | np.ndarray, probabilities: list[float] | np.ndarray, *, bins: int = 10
) -> EvaluationMetrics:
    y_true = np.asarray(targets, dtype=int)
    y_probability = np.clip(np.asarray(probabilities, dtype=float), 1e-9, 1 - 1e-9)
    if len(y_true) == 0:
        raise ValueError("evaluation requires at least one sample")
    if len(y_true) != len(y_probability):
        raise ValueError("targets and probabilities must have the same length")
    predictions = (y_probability >= 0.5).astype(int)
    auc = float(roc_auc_score(y_true, y_probability)) if len(np.unique(y_true)) > 1 else None
    return EvaluationMetrics(
        accuracy=float(accuracy_score(y_true, predictions)),
        log_loss=float(log_loss(y_true, y_probability, labels=[0, 1])),
        brier_score=float(brier_score_loss(y_true, y_probability)),
        roc_auc=auc,
        expected_calibration_error=expected_calibration_error(y_true, y_probability, bins=bins),
        sample_size=len(y_true),
    )


def expected_calibration_error(y_true: np.ndarray, probabilities: np.ndarray, *, bins: int = 10) -> float:
    if bins < 1:
        raise ValueError("bins must be at least one")
    boundaries = np.linspace(0, 1, bins + 1)
    total = len(y_true)
    error = 0.0
    for index in range(bins):
        upper_inclusive = index == bins - 1
        mask = (probabilities >= boundaries[index]) & (
            probabilities <= boundaries[index + 1]
            if upper_inclusive
            else probabilities < boundaries[index + 1]
        )
        if np.any(mask):
            observed = float(np.mean(y_true[mask]))
            predicted = float(np.mean(probabilities[mask]))
            error += float(np.sum(mask)) / total * abs(observed - predicted)
    return error
