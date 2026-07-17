import numpy as np

from app.phase3.training_dataset import numeric_value


def elo_win_probability(elo_difference: float) -> float:
    return 1.0 / (1.0 + 10 ** (-elo_difference / 400.0))


def predict_elo_probabilities(rows: list[dict[str, object]]) -> np.ndarray:
    return np.asarray(
        [elo_win_probability(numeric_value(row["elo_difference"], field="elo_difference")) for row in rows],
        dtype=float,
    )
