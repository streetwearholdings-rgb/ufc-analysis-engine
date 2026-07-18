"""Create the Phase 2 analysis schema."""

from collections.abc import Sequence

from alembic import op
from app.database import models  # noqa: F401
from app.database.base import Base

revision: str = "20260716_0001"
down_revision: str | None = None
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

LATER_PHASE_TABLES = {
    "fighter_feature_snapshots",
    "fight_training_records",
    "odds_provider_events",
    "odds_snapshots",
    "context_sources",
    "context_documents",
    "context_signals",
    "context_signal_sources",
    "context_reviews",
    "context_feature_values",
    "context_adjustments",
    "fighter_aliases",
    "ingestion_runs",
}


def upgrade() -> None:
    phase2_tables = [
        table
        for table in Base.metadata.sorted_tables
        if table.name not in LATER_PHASE_TABLES
    ]
    Base.metadata.create_all(bind=op.get_bind(), tables=phase2_tables, checkfirst=False)


def downgrade() -> None:
    phase2_tables = [
        table
        for table in Base.metadata.sorted_tables
        if table.name not in LATER_PHASE_TABLES
    ]
    Base.metadata.drop_all(bind=op.get_bind(), tables=phase2_tables, checkfirst=False)
