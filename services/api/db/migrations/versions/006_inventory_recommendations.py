"""inventory_recommendations table — Sprint 3

Revision ID: 006
Revises: 005
Create Date: 2026-06-15

Stores computed inventory intelligence per variant per run_date.  The unique
constraint is on (variant_id, run_date) so at most one recommendation row exists
per SKU per calendar day.  On conflict the row is overwritten with the latest run's
values (run_at is updated to reflect the most recent computation time).

run_at (TIMESTAMPTZ) records exactly when the recommendation was computed — useful
for "recommendations last updated X minutes ago" UI display.

All calculation inputs are stored alongside outputs to create a full audit trail.
The risk_tier CHECK constraint is the authoritative list of valid tiers.

Three indexes cover the three common query patterns:
  - Dashboard list: all SKUs for a brand, ordered by days_cover ASC
  - Filtered list: SKUs for a brand filtered by risk_tier
  - Detail/history: single SKU history over time
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "inventory_recommendations",
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
        sa.Column("run_date", sa.Date, nullable=False),
        sa.Column(
            "run_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        # ── Inputs captured at run time ──────────────────────────────────────
        sa.Column("available", sa.Integer, nullable=False),
        sa.Column("lead_time_days", sa.Integer, nullable=False),
        sa.Column("target_cover_days", sa.Integer, nullable=False),
        sa.Column("review_period_days", sa.Integer, nullable=False),
        sa.Column("z_score", sa.Numeric(6, 3), nullable=False),
        sa.Column("in_stock_days_90d", sa.Integer, nullable=False),
        # ── Demand model ─────────────────────────────────────────────────────
        sa.Column("avg_daily_demand", sa.Numeric(10, 4), nullable=False),
        sa.Column("demand_std_daily", sa.Numeric(10, 4), nullable=False),
        # ── Computed outputs ──────────────────────────────────────────────────
        sa.Column("days_cover", sa.Numeric(10, 2), nullable=True),
        sa.Column("stockout_date", sa.Date, nullable=True),
        sa.Column("safety_stock", sa.Numeric(10, 2), nullable=False),
        sa.Column("reorder_point", sa.Numeric(10, 2), nullable=False),
        sa.Column("recommended_order_qty", sa.Integer, nullable=True),
        sa.Column(
            "is_emergency_order",
            sa.Boolean,
            nullable=False,
            server_default="false",
        ),
        sa.Column("overstock_units", sa.Integer, nullable=True),
        sa.Column("excess_cover_days", sa.Numeric(10, 2), nullable=True),
        sa.Column(
            "dead_stock",
            sa.Boolean,
            nullable=False,
            server_default="false",
        ),
        # ── Classification ────────────────────────────────────────────────────
        sa.Column("risk_tier", sa.Text, nullable=False),
        sa.Column("recommended_action", sa.Text, nullable=False),
        # ── Value metrics (NULL until cost_price is available) ────────────────
        sa.Column("revenue_at_risk", sa.Numeric(12, 2), nullable=True),
        sa.Column("capital_trapped", sa.Numeric(12, 2), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "variant_id",
            "run_date",
            name="uq_inv_rec_variant_date",
        ),
        sa.CheckConstraint(
            "risk_tier IN ('stockout','reorder','healthy','overstock','dead')",
            name="chk_inv_rec_risk_tier",
        ),
    )

    # Dashboard list: brand + date ordered by urgency (days_cover ASC NULLS LAST)
    op.create_index(
        "idx_inv_rec_brand_date_cover",
        "inventory_recommendations",
        ["brand_id", sa.text("run_date DESC"), sa.text("days_cover ASC NULLS LAST")],
    )
    # Filtered list by risk_tier
    op.create_index(
        "idx_inv_rec_brand_date_tier",
        "inventory_recommendations",
        ["brand_id", "run_date", "risk_tier"],
    )
    # Single-variant history
    op.create_index(
        "idx_inv_rec_variant_date",
        "inventory_recommendations",
        ["variant_id", sa.text("run_date DESC")],
    )

    op.execute("ALTER TABLE inventory_recommendations ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE inventory_recommendations FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY tenant_isolation ON inventory_recommendations
          USING      (brand_id = current_setting('app.current_brand', true)::uuid)
          WITH CHECK (brand_id = current_setting('app.current_brand', true)::uuid)
    """)
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON inventory_recommendations TO threados_app"
    )


def downgrade() -> None:
    op.drop_index("idx_inv_rec_variant_date", table_name="inventory_recommendations")
    op.drop_index("idx_inv_rec_brand_date_tier", table_name="inventory_recommendations")
    op.drop_index("idx_inv_rec_brand_date_cover", table_name="inventory_recommendations")
    op.drop_table("inventory_recommendations")
