"""inventory_settings table — Sprint 3

Revision ID: 004
Revises: 003
Create Date: 2026-06-15

Stores brand-level inventory policy defaults (lead time, target cover, service
level).  Per-SKU overrides live in the variant_settings table (migration 005).
All values have sensible defaults so existing brands work without configuration.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "inventory_settings",
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
            unique=True,
        ),
        sa.Column("default_lead_time", sa.Integer, nullable=False, server_default="14"),
        sa.Column("target_cover_days", sa.Integer, nullable=False, server_default="30"),
        sa.Column("review_period_days", sa.Integer, nullable=False, server_default="7"),
        sa.Column(
            "service_level",
            sa.Numeric(4, 3),
            nullable=False,
            server_default="0.950",
        ),
        sa.Column(
            "dead_stock_threshold_days",
            sa.Integer,
            nullable=False,
            server_default="90",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.execute("ALTER TABLE inventory_settings ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE inventory_settings FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY tenant_isolation ON inventory_settings
          USING      (brand_id = current_setting('app.current_brand', true)::uuid)
          WITH CHECK (brand_id = current_setting('app.current_brand', true)::uuid)
    """)
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON inventory_settings TO threados_app"
    )


def downgrade() -> None:
    op.drop_table("inventory_settings")
