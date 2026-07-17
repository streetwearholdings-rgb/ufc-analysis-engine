"""Add Phase 3 historical snapshots and training records."""

from collections.abc import Sequence

from alembic import op
from app.database.models.fight_training_record import FightTrainingRecord
from app.database.models.fighter_feature_snapshot import FighterFeatureSnapshot

revision: str = "20260717_0002"
down_revision: str | None = "20260716_0001"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    FighterFeatureSnapshot.__table__.create(bind=bind, checkfirst=True)
    FightTrainingRecord.__table__.create(bind=bind, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    FightTrainingRecord.__table__.drop(bind=bind, checkfirst=True)
    FighterFeatureSnapshot.__table__.drop(bind=bind, checkfirst=True)
