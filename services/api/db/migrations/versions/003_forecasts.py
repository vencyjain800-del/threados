"""Forecast storage — Sprint 3 Phase D

Revision ID: 003
Revises: 002
Create Date: 2026-06-11

Adds the ``forecasts`` table that stores per-variant daily demand forecasts
produced by the nightly forecasting worker job.

Design notes
------------
* UNIQUE (variant_id, forecast_date, run_date) — one forecast point per
  variant per horizon date per job run.  Re-running the forecast job for
  the same brand and run_date is safe: ON CONFLICT DO UPDATE overwrites
  the previous values.
* ix_forecasts_brand_run — covers the common API query
  WHERE brand_id = ? AND run_date = ? to fetch the latest run.
* RLS pattern mirrors all other data tables (ENABLE + FORCE, brand_id
  policy keyed on app.current_brand GUC).
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "forecasts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "brand_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("brands.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "variant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("variants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("forecast_date", sa.Date, nullable=False),
        sa.Column("run_date", sa.Date, nullable=False),
        sa.Column("predicted_units", sa.Numeric(10, 2), nullable=False),
        sa.Column("lower_bound", sa.Numeric(10, 2), nullable=False),
        sa.Column("upper_bound", sa.Numeric(10, 2), nullable=False),
        sa.Column("model_name", sa.Text, nullable=False),
        sa.UniqueConstraint(
            "variant_id",
            "forecast_date",
            "run_date",
            name="uq_forecasts_variant_date_run",
        ),
    )

    op.create_index(
        "ix_forecasts_brand_run",
        "forecasts",
        ["brand_id", "run_date"],
    )

    # RLS — same pattern as all other data tables: ENABLE + FORCE so even
    # the owner role (threados_migrate) is subject to the policy when acting
    # as the runtime role.  threados_migrate has rolbypassrls=True so it can
    # still INSERT during worker jobs without setting the GUC.
    op.execute("ALTER TABLE forecasts ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE forecasts FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY tenant_isolation ON forecasts
          USING      (brand_id = current_setting('app.current_brand', true)::uuid)
          WITH CHECK (brand_id = current_setting('app.current_brand', true)::uuid)
    """)

    # Grant the runtime app role access to the new table.
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON forecasts TO threados_app"
    )


def downgrade() -> None:
    op.drop_index("ix_forecasts_brand_run", table_name="forecasts")
    op.drop_table("forecasts")
