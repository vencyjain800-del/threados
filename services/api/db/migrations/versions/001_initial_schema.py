"""Initial ThreadOS schema — Sprint 1 foundation

Revision ID: 001
Revises:
Create Date: 2026-06-06
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Extensions
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.execute("CREATE EXTENSION IF NOT EXISTS citext")

    # Enums
    op.execute("CREATE TYPE user_role AS ENUM ('owner','admin','member','viewer')")
    op.execute("CREATE TYPE sync_status AS ENUM ('queued','running','succeeded','failed','partial')")

    # brands
    op.create_table(
        "brands",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("country", sa.String(2), nullable=False, server_default="GB"),
        sa.Column("currency", sa.String(3), nullable=False, server_default="GBP"),
        sa.Column("plan", sa.Text, nullable=False, server_default="starter"),
        sa.Column("data_sharing_consent", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("consent_scope", sa.Text, nullable=True),
        sa.Column("onboarded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    # users
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("email", sa.Text, nullable=False, unique=True),
        sa.Column("name", sa.Text, nullable=True),
        sa.Column("password_hash", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.execute("ALTER TABLE users ALTER COLUMN email TYPE citext")

    # brand_users
    op.create_table(
        "brand_users",
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brands.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("role", postgresql.ENUM("owner", "admin", "member", "viewer", name="user_role", create_type=False), nullable=False, server_default="owner"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    # sessions
    op.create_table(
        "sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brands.id"), nullable=True),
        sa.Column("token_hash", postgresql.BYTEA, nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_sessions_user", "sessions", ["user_id"])

    # shopify_connections
    op.create_table(
        "shopify_connections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brands.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("shop_domain", sa.Text, nullable=False, unique=True),
        sa.Column("access_token_enc", postgresql.BYTEA, nullable=False),
        sa.Column("scopes", sa.Text, nullable=False),
        sa.Column("installed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("uninstalled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("webhook_ids", postgresql.JSONB, nullable=False, server_default="[]"),
    )

    # sync_runs
    op.create_table(
        "sync_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brands.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.Text, nullable=False),
        sa.Column("status", postgresql.ENUM("queued", "running", "succeeded", "failed", "partial", name="sync_status", create_type=False), nullable=False, server_default="queued"),
        sa.Column("entities", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    # products
    op.create_table(
        "products",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brands.id", ondelete="CASCADE"), nullable=False),
        sa.Column("shopify_id", sa.BigInteger, nullable=False),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("product_type", sa.Text, nullable=True),
        sa.Column("vendor", sa.Text, nullable=True),
        sa.Column("status", sa.Text, nullable=True),
        sa.Column("created_at_shop", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("brand_id", "shopify_id"),
    )

    # variants
    op.create_table(
        "variants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brands.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("shopify_id", sa.BigInteger, nullable=False),
        sa.Column("sku", sa.Text, nullable=True),
        sa.Column("title", sa.Text, nullable=True),
        sa.Column("option_color", sa.Text, nullable=True),
        sa.Column("option_size", sa.Text, nullable=True),
        sa.Column("price", sa.Numeric(12, 2), nullable=True),
        sa.Column("cost", sa.Numeric(12, 2), nullable=True),
        sa.Column("barcode", sa.Text, nullable=True),
        sa.Column("first_sold_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("brand_id", "shopify_id"),
    )
    op.create_index("ix_variants_brand", "variants", ["brand_id"])

    # collections
    op.create_table(
        "collections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brands.id", ondelete="CASCADE"), nullable=False),
        sa.Column("shopify_id", sa.BigInteger, nullable=False),
        sa.Column("title", sa.Text, nullable=False),
        sa.UniqueConstraint("brand_id", "shopify_id"),
    )

    # product_collections
    op.create_table(
        "product_collections",
        sa.Column("product_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("products.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("collection_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("collections.id", ondelete="CASCADE"), primary_key=True),
    )

    # orders
    op.create_table(
        "orders",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brands.id", ondelete="CASCADE"), nullable=False),
        sa.Column("shopify_id", sa.BigInteger, nullable=False),
        sa.Column("ordered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("financial_status", sa.Text, nullable=True),
        sa.Column("channel", sa.Text, nullable=True),
        sa.Column("discount_total", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.UniqueConstraint("brand_id", "shopify_id"),
    )
    op.create_index("ix_orders_brand_time", "orders", ["brand_id", "ordered_at"])

    # order_line_items
    op.create_table(
        "order_line_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brands.id", ondelete="CASCADE"), nullable=False),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("variant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("variants.id"), nullable=True),
        sa.Column("quantity", sa.Integer, nullable=False),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("discount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("refunded_qty", sa.Integer, nullable=False, server_default="0"),
    )
    op.create_index("ix_oli_variant", "order_line_items", ["variant_id"])

    # inventory_levels
    op.create_table(
        "inventory_levels",
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brands.id", ondelete="CASCADE"), nullable=False),
        sa.Column("variant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("variants.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("location_id", sa.BigInteger, primary_key=True),
        sa.Column("available", sa.Integer, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    # inventory_snapshots
    op.create_table(
        "inventory_snapshots",
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brands.id", ondelete="CASCADE"), nullable=False),
        sa.Column("variant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("variants.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("snap_date", sa.Date, primary_key=True),
        sa.Column("available", sa.Integer, nullable=False),
    )

    # sales_daily
    op.create_table(
        "sales_daily",
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brands.id", ondelete="CASCADE"), nullable=False),
        sa.Column("variant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("variants.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("sale_date", sa.Date, primary_key=True),
        sa.Column("units_sold", sa.Integer, nullable=False, server_default="0"),
        sa.Column("gross_revenue", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("avg_discount", sa.Numeric(6, 4), nullable=False, server_default="0"),
        sa.Column("was_in_stock", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("was_on_promo", sa.Boolean, nullable=False, server_default="false"),
    )
    op.create_index("ix_sales_brand_date", "sales_daily", ["brand_id", "sale_date"])

    # audit_log
    op.create_table(
        "audit_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.Text, nullable=False),
        sa.Column("target", sa.Text, nullable=True),
        sa.Column("meta", postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    # ── RLS: enable on all tenant tables ─────────────────────────────────────
    # Auth tables (sessions, brands, brand_users) get ENABLE only — NOT FORCE.
    # This allows the table-owner role (threados_migrate) to bypass RLS on them,
    # which is required for auth bootstrapping (session verification, signup, login)
    # where no tenant GUC is set yet. The runtime role (threados_app) still sees
    # only its own rows because it is not the owner and is subject to RLS policies.
    #
    # Data tables get both ENABLE and FORCE — even the owner cannot bypass them.
    # This is defence-in-depth for actual tenant business data.
    auth_tables = ["brands", "brand_users", "sessions"]
    for table in auth_tables:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        # Intentionally NO FORCE — owner role bypasses for auth bootstrapping

    data_tables = [
        "shopify_connections", "sync_runs",
        "products", "variants", "collections", "product_collections",
        "orders", "order_line_items",
        "inventory_levels", "inventory_snapshots",
        "sales_daily",
    ]
    for table in data_tables:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")

    # brands is the root — accessible when brand_id matches OR when viewing own brand row
    op.execute("""
        CREATE POLICY tenant_isolation ON brands
          USING      (id = current_setting('app.current_brand', true)::uuid)
          WITH CHECK (id = current_setting('app.current_brand', true)::uuid)
    """)

    rls_tables = [
        "brand_users", "sessions",
        "shopify_connections", "sync_runs",
        "products", "variants", "collections",
        "orders", "order_line_items",
        "inventory_levels", "inventory_snapshots",
        "sales_daily",
    ]
    for table in rls_tables:
        op.execute(f"""
            CREATE POLICY tenant_isolation ON {table}
              USING      (brand_id = current_setting('app.current_brand', true)::uuid)
              WITH CHECK (brand_id = current_setting('app.current_brand', true)::uuid)
        """)

    # product_collections has no brand_id — join-table, protected through its parents
    op.execute("""
        CREATE POLICY tenant_isolation ON product_collections
          USING (
            EXISTS (
              SELECT 1 FROM products p
              WHERE p.id = product_id
                AND p.brand_id = current_setting('app.current_brand', true)::uuid
            )
          )
          WITH CHECK (
            EXISTS (
              SELECT 1 FROM products p
              WHERE p.id = product_id
                AND p.brand_id = current_setting('app.current_brand', true)::uuid
            )
          )
    """)

    # Grant runtime role access (threados_app must exist before migration runs)
    op.execute("GRANT USAGE ON SCHEMA public TO threados_app")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO threados_app")
    op.execute("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO threados_app")


def downgrade() -> None:
    tables = [
        "audit_log", "sales_daily", "inventory_snapshots", "inventory_levels",
        "order_line_items", "orders", "product_collections", "collections",
        "variants", "products", "sync_runs", "shopify_connections",
        "sessions", "brand_users", "users", "brands",
    ]
    for table in tables:
        op.drop_table(table)

    op.execute("DROP TYPE IF EXISTS sync_status")
    op.execute("DROP TYPE IF EXISTS user_role")
    op.execute("DROP EXTENSION IF EXISTS citext")
    op.execute("DROP EXTENSION IF EXISTS pgcrypto")
