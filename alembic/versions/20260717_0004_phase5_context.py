"""Add Phase 5 Context Engine audit and calculation tables."""

from collections.abc import Sequence

from alembic import op
from app.database.models.context import (
    ContextAdjustment,
    ContextDocument,
    ContextFeatureValue,
    ContextReview,
    ContextSignal,
    ContextSignalSource,
    ContextSource,
    FighterAlias,
)

revision: str = "20260717_0004"
down_revision: str | None = "20260717_0003"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

TABLES = [
    ContextSource,
    ContextDocument,
    ContextSignal,
    ContextSignalSource,
    ContextReview,
    ContextFeatureValue,
    ContextAdjustment,
    FighterAlias,
]


def upgrade() -> None:
    bind = op.get_bind()
    for model in TABLES:
        model.__table__.create(bind=bind, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    for model in reversed(TABLES):
        model.__table__.drop(bind=bind, checkfirst=True)
