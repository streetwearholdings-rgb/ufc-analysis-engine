def percentile_rank(value: float, population: list[float]) -> float:
    """Return a tie-aware percentile on a 0–100 scale."""
    if not population:
        return 50.0
    below = sum(item < value for item in population)
    equal = sum(item == value for item in population)
    return 100.0 * (below + 0.5 * equal) / len(population)


def shrink_toward_midpoint(score: float, reliability: float, midpoint: float = 50.0) -> float:
    reliability = min(1.0, max(0.0, reliability))
    return midpoint + (score - midpoint) * reliability
