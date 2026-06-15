"""variant_settings table — Sprint 3

Revision ID: 005
Revises: 004
Create Date: 2026-06-15

Per-SKU overrides for the inventory intelligence layer.  Each column is nullable:
a NULL value means "inherit the brand default from inventory_settings".  The
recommendation job resolves effective values using COALESCE(override, brand_default).

supplier_name is free text in Phase 1.  A future migration will add a supplier_id
FK once the suppliers table exists, migrating existing supplier_name values.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "variant_settings",
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
        sa.Column("lead_time_days", sa.Integer, nullable=True),
        sa.Column("target_cover_days", sa.Integer, nullable=True),
        sa.Column("cost_price", sa.Numeric(10, 2), nullable=True),
        sa.Column("supplier_name", sa.Text, nullable=True),
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
        sa.UniqueConstraint("brand_id", "variant_id", name="uq_variant_settings_variant"),
    )

    op.execute("ALTER TABLE variant_settings ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE variant_settings FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY tenant_isolation ON variant_settings
          USING      (brand_id = current_setting('app.current_brand', true)::uuid)
          WITH CHECK (brand_id = current_setting('app.current_brand', true)::uuid)
    """)
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON variant_settings TO threados_app"
    )


def downgrade() -> None:
    op.drop_table("variant_settings")
