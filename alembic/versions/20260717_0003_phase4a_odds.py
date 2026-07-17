"""Add Phase 4A provider events and immutable odds snapshots."""

from collections.abc import Sequence

from alembic import op
from app.database.models.odds_provider_event import OddsProviderEvent
from app.database.models.odds_snapshot import OddsSnapshot

revision: str = "20260717_0003"
down_revision: str | None = "20260717_0002"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    OddsProviderEvent.__table__.create(bind=bind, checkfirst=True)
    OddsSnapshot.__table__.create(bind=bind, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    OddsSnapshot.__table__.drop(bind=bind, checkfirst=True)
    OddsProviderEvent.__table__.drop(bind=bind, checkfirst=True)
