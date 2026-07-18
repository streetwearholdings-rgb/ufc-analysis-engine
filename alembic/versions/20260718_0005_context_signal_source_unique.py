"""Add the context signal/source uniqueness constraint."""

from collections.abc import Sequence

from alembic import op

revision: str = "20260718_0005"
down_revision: str | None = "20260717_0004"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_context_signal_sources_context_signal_id",
        "context_signal_sources",
        ["context_signal_id", "context_source_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_context_signal_sources_context_signal_id",
        "context_signal_sources",
        type_="unique",
    )
