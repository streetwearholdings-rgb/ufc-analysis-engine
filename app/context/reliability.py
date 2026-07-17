from decimal import Decimal

from app.context.enums import SourceType
from app.context.registry import SOURCE_RELIABILITY


def get_default_source_reliability(source_type: SourceType) -> Decimal:
    return Decimal(str(SOURCE_RELIABILITY[source_type]))


def calculate_effective_source_reliability(source_type: SourceType, override: Decimal | None = None) -> Decimal:
    if override is not None and not Decimal(0) <= override <= Decimal(1):
        raise ValueError("source reliability override must be between zero and one")
    return override if override is not None else get_default_source_reliability(source_type)
