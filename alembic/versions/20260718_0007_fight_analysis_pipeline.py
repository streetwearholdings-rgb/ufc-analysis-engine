"""Add production analysis runs and fight analysis history."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260718_0007"
down_revision: str | None = "20260718_0006"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "analysis_runs",
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("model_type", sa.String(length=80), nullable=False),
        sa.Column("model_version", sa.String(length=50), nullable=False),
        sa.Column("probability_method", sa.String(length=120), nullable=False),
        sa.Column("calibration_status", sa.String(length=40), nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("events_processed", sa.Integer(), nullable=False),
        sa.Column("fights_found", sa.Integer(), nullable=False),
        sa.Column("fights_analysed", sa.Integer(), nullable=False),
        sa.Column("recommendations_created", sa.Integer(), nullable=False),
        sa.Column("no_bets", sa.Integer(), nullable=False),
        sa.Column("insufficient_data", sa.Integer(), nullable=False),
        sa.Column("failed", sa.Integer(), nullable=False),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], name=op.f("fk_analysis_runs_event_id_events")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_analysis_runs")),
    )
    for column in ("status", "model_version", "event_id", "started_at"):
        op.create_index(op.f(f"ix_analysis_runs_{column}"), "analysis_runs", [column])

    op.create_table(
        "fight_analyses",
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("fight_id", sa.Uuid(), nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("scheduled_at", sa.Date(), nullable=False),
        sa.Column("fighter_a_id", sa.Uuid(), nullable=False),
        sa.Column("fighter_b_id", sa.Uuid(), nullable=False),
        sa.Column("predicted_winner_id", sa.Uuid(), nullable=True),
        sa.Column("predicted_loser_id", sa.Uuid(), nullable=True),
        sa.Column("model_probability", sa.Numeric(12, 8), nullable=True),
        sa.Column("opponent_probability", sa.Numeric(12, 8), nullable=True),
        sa.Column("market_probability", sa.Numeric(12, 8), nullable=True),
        sa.Column("no_vig_market_probability", sa.Numeric(12, 8), nullable=True),
        sa.Column("decimal_odds", sa.Numeric(10, 4), nullable=True),
        sa.Column("value_edge", sa.Numeric(12, 8), nullable=True),
        sa.Column("expected_value", sa.Numeric(12, 8), nullable=True),
        sa.Column("confidence_score", sa.Numeric(5, 4), nullable=True),
        sa.Column("confidence_tier", sa.String(length=30), nullable=False),
        sa.Column("feature_quality_score", sa.Numeric(5, 4), nullable=True),
        sa.Column("risk_level", sa.String(length=30), nullable=False),
        sa.Column("recommendation", sa.String(length=30), nullable=False),
        sa.Column("recommendation_status", sa.String(length=30), nullable=False),
        sa.Column("recommended_side_id", sa.Uuid(), nullable=True),
        sa.Column("recommended_market", sa.String(length=30), nullable=True),
        sa.Column("no_bet_reason", sa.Text(), nullable=True),
        sa.Column("odds_snapshot_id", sa.Uuid(), nullable=True),
        sa.Column("odds_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("data_freshness_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("key_advantages", sa.JSON(), nullable=False),
        sa.Column("key_risks", sa.JSON(), nullable=False),
        sa.Column("warnings", sa.JSON(), nullable=False),
        sa.Column("model_type", sa.String(length=80), nullable=False),
        sa.Column("model_version", sa.String(length=50), nullable=False),
        sa.Column("probability_method", sa.String(length=120), nullable=False),
        sa.Column("calibration_status", sa.String(length=40), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["analysis_runs.id"], name=op.f("fk_fight_analyses_run_id_analysis_runs")),
        sa.ForeignKeyConstraint(["fight_id"], ["fights.id"], name=op.f("fk_fight_analyses_fight_id_fights")),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], name=op.f("fk_fight_analyses_event_id_events")),
        sa.ForeignKeyConstraint(
            ["fighter_a_id"], ["fighters.id"], name=op.f("fk_fight_analyses_fighter_a_id_fighters")
        ),
        sa.ForeignKeyConstraint(
            ["fighter_b_id"], ["fighters.id"], name=op.f("fk_fight_analyses_fighter_b_id_fighters")
        ),
        sa.ForeignKeyConstraint(
            ["predicted_winner_id"],
            ["fighters.id"],
            name=op.f("fk_fight_analyses_predicted_winner_id_fighters"),
        ),
        sa.ForeignKeyConstraint(
            ["predicted_loser_id"],
            ["fighters.id"],
            name=op.f("fk_fight_analyses_predicted_loser_id_fighters"),
        ),
        sa.ForeignKeyConstraint(
            ["recommended_side_id"],
            ["fighters.id"],
            name=op.f("fk_fight_analyses_recommended_side_id_fighters"),
        ),
        sa.ForeignKeyConstraint(
            ["odds_snapshot_id"],
            ["odds_snapshots.id"],
            name=op.f("fk_fight_analyses_odds_snapshot_id_odds_snapshots"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_fight_analyses")),
    )
    for column in ("run_id", "fight_id", "event_id", "recommendation_status", "model_version", "generated_at"):
        op.create_index(op.f(f"ix_fight_analyses_{column}"), "fight_analyses", [column])
    op.create_index("ix_fight_analyses_fight_generated", "fight_analyses", ["fight_id", "generated_at"])
    op.create_index("ix_fight_analyses_status_active", "fight_analyses", ["recommendation_status", "active"])


def downgrade() -> None:
    op.drop_table("fight_analyses")
    op.drop_table("analysis_runs")
