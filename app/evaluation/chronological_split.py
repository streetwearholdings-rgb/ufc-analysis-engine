from dataclasses import dataclass
from datetime import date
from typing import Any


@dataclass(frozen=True, slots=True)
class ChronologicalSplit:
    train: list[dict[str, Any]]
    validation: list[dict[str, Any]]
    test: list[dict[str, Any]]


def split_by_date(
    rows: list[dict[str, Any]], *, train_end: date, validation_end: date
) -> ChronologicalSplit:
    if train_end >= validation_end:
        raise ValueError("train_end must be before validation_end")
    ordered = sorted(rows, key=lambda row: (row["event_date"], str(row["fight_id"])))
    train = [row for row in ordered if row["event_date"] <= train_end]
    validation = [row for row in ordered if train_end < row["event_date"] <= validation_end]
    test = [row for row in ordered if row["event_date"] > validation_end]
    return ChronologicalSplit(train, validation, test)


def proportional_chronological_split(
    rows: list[dict[str, Any]], train_fraction: float = 0.6, validation_fraction: float = 0.2
) -> ChronologicalSplit:
    if not 0 < train_fraction < 1 or not 0 < validation_fraction < 1:
        raise ValueError("split fractions must be between zero and one")
    if train_fraction + validation_fraction >= 1:
        raise ValueError("train and validation fractions must leave a test period")
    ordered = sorted(rows, key=lambda row: (row["event_date"], str(row["fight_id"])))
    train_end = max(1, int(len(ordered) * train_fraction))
    validation_end = max(train_end + 1, int(len(ordered) * (train_fraction + validation_fraction)))
    return ChronologicalSplit(ordered[:train_end], ordered[train_end:validation_end], ordered[validation_end:])


def walk_forward_splits(
    rows: list[dict[str, Any]], *, minimum_train_size: int, validation_size: int, test_size: int
) -> list[ChronologicalSplit]:
    ordered = sorted(rows, key=lambda row: (row["event_date"], str(row["fight_id"])))
    splits: list[ChronologicalSplit] = []
    cursor = minimum_train_size
    while cursor + validation_size + test_size <= len(ordered):
        splits.append(
            ChronologicalSplit(
                ordered[:cursor],
                ordered[cursor : cursor + validation_size],
                ordered[cursor + validation_size : cursor + validation_size + test_size],
            )
        )
        cursor += test_size
    return splits
