"""Add ingestion status and allow unknown upcoming bout metadata."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260718_0006"
down_revision: str | None = "20260718_0005"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("fights") as batch_op:
        batch_op.alter_column("weight_class", existing_type=sa.String(length=50), nullable=True)
        batch_op.alter_column("scheduled_rounds", existing_type=sa.Integer(), nullable=True)

    op.create_table(
        "ingestion_runs",
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("events_processed", sa.Integer(), nullable=False),
        sa.Column("fights_processed", sa.Integer(), nullable=False),
        sa.Column("fighters_processed", sa.Integer(), nullable=False),
        sa.Column("odds_processed", sa.Integer(), nullable=False),
        sa.Column("records", sa.JSON(), nullable=False),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ingestion_runs")),
    )
    op.create_index(op.f("ix_ingestion_runs_provider"), "ingestion_runs", ["provider"])
    op.create_index(op.f("ix_ingestion_runs_started_at"), "ingestion_runs", ["started_at"])
    op.create_index(op.f("ix_ingestion_runs_status"), "ingestion_runs", ["status"])


def downgrade() -> None:
    op.drop_index(op.f("ix_ingestion_runs_status"), table_name="ingestion_runs")
    op.drop_index(op.f("ix_ingestion_runs_started_at"), table_name="ingestion_runs")
    op.drop_index(op.f("ix_ingestion_runs_provider"), table_name="ingestion_runs")
    op.drop_table("ingestion_runs")
    with op.batch_alter_table("fights") as batch_op:
        batch_op.alter_column("scheduled_rounds", existing_type=sa.Integer(), nullable=False)
        batch_op.alter_column("weight_class", existing_type=sa.String(length=50), nullable=False)
