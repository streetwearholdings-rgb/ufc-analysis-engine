from datetime import date
from math import exp, log


def decay_lambda(half_life_days: float) -> float:
    if half_life_days <= 0:
        raise ValueError("half-life must be positive")
    return log(2.0) / half_life_days


def recency_weight(fight_date: date, as_of: date, half_life_days: float = 730.0) -> float:
    if fight_date > as_of:
        raise ValueError("fight date cannot be after the calculation date")
    return exp(-decay_lambda(half_life_days) * (as_of - fight_date).days)
