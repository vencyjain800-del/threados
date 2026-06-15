"""
Minimal SQLAlchemy Core Table definitions for the worker.

These are NOT ORM models — just enough column metadata to enable
``pg_insert().on_conflict_do_update().returning()`` without importing
anything from services/api.

Only columns that are actively read or written by the worker are declared.
"""
from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    Integer,
    MetaData,
    Numeric,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID

metadata = MetaData()

products = Table(
    "products",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("brand_id", UUID(as_uuid=True), nullable=False),
    Column("shopify_id", BigInteger, nullable=False),
    Column("title", Text, nullable=False),
    Column("product_type", Text),
    Column("vendor", Text),
    Column("status", Text),
    Column("created_at_shop", DateTime(timezone=True)),
)

variants = Table(
    "variants",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("brand_id", UUID(as_uuid=True), nullable=False),
    Column("product_id", UUID(as_uuid=True), nullable=False),
    Column("shopify_id", BigInteger, nullable=False),
    Column("sku", Text),
    Column("title", Text),
    Column("option_color", Text),
    Column("option_size", Text),
    Column("price", Numeric(12, 2)),
    Column("barcode", Text),
    # Added in migration 002: links a variant to its Shopify inventory tracking record.
    # Populated by the worker upsert; used to resolve inventory_levels/update webhooks.
    Column("inventory_item_id", BigInteger, nullable=True),
)

collections = Table(
    "collections",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("brand_id", UUID(as_uuid=True), nullable=False),
    Column("shopify_id", BigInteger, nullable=False),
    Column("title", Text, nullable=False),
)

product_collections = Table(
    "product_collections",
    metadata,
    # Composite PK — no brand_id; RLS is enforced through the parent product
    Column("product_id", UUID(as_uuid=True), primary_key=True),
    Column("collection_id", UUID(as_uuid=True), primary_key=True),
)

orders = Table(
    "orders",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("brand_id", UUID(as_uuid=True), nullable=False),
    Column("shopify_id", BigInteger, nullable=False),
    Column("ordered_at", DateTime(timezone=True), nullable=False),
    Column("financial_status", Text),
    Column("channel", Text),
    Column("discount_total", Numeric(12, 2), nullable=False),
)

order_line_items = Table(
    "order_line_items",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("brand_id", UUID(as_uuid=True), nullable=False),
    Column("order_id", UUID(as_uuid=True), nullable=False),
    Column("variant_id", UUID(as_uuid=True)),  # nullable — deleted Shopify variants
    Column("quantity", Integer, nullable=False),
    Column("unit_price", Numeric(12, 2)),
    Column("discount", Numeric(12, 2), nullable=False),
    Column("refunded_qty", Integer, nullable=False, server_default="0"),
)

inventory_levels = Table(
    "inventory_levels",
    metadata,
    Column("brand_id", UUID(as_uuid=True), nullable=False),
    Column("variant_id", UUID(as_uuid=True), primary_key=True),
    Column("location_id", BigInteger, primary_key=True),
    Column("available", Integer, nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)

# ── Aggregation tables (written by aggregation.py) ────────────────────────────

sales_daily = Table(
    "sales_daily",
    metadata,
    Column("brand_id", UUID(as_uuid=True), nullable=False),
    # Composite PK: (variant_id, sale_date)
    Column("variant_id", UUID(as_uuid=True), primary_key=True),
    Column("sale_date", Date, primary_key=True),
    Column("units_sold", Integer, nullable=False),
    Column("gross_revenue", Numeric(12, 2), nullable=False),
    Column("avg_discount", Numeric(6, 4), nullable=False),
    Column("was_in_stock", Boolean, nullable=False),
    Column("was_on_promo", Boolean, nullable=False),
)

inventory_snapshots = Table(
    "inventory_snapshots",
    metadata,
    Column("brand_id", UUID(as_uuid=True), nullable=False),
    # Composite PK: (variant_id, snap_date)
    Column("variant_id", UUID(as_uuid=True), primary_key=True),
    Column("snap_date", Date, primary_key=True),
    Column("available", Integer, nullable=False),
)

# ── Forecast table (written by forecast.py) ───────────────────────────────────

forecasts = Table(
    "forecasts",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("brand_id", UUID(as_uuid=True), nullable=False),
    Column("variant_id", UUID(as_uuid=True), nullable=False),
    Column("forecast_date", Date, nullable=False),
    Column("run_date", Date, nullable=False),
    Column("predicted_units", Numeric(10, 2), nullable=False),
    Column("lower_bound", Numeric(10, 2), nullable=False),
    Column("upper_bound", Numeric(10, 2), nullable=False),
    Column("model_name", Text, nullable=False),
    UniqueConstraint(
        "variant_id", "forecast_date", "run_date",
        name="uq_forecasts_variant_date_run",
    ),
)

# ── Inventory intelligence tables (written by recommendations.py) ─────────────

inventory_settings = Table(
    "inventory_settings",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("brand_id", UUID(as_uuid=True), nullable=False),
    Column("default_lead_time", Integer, nullable=False),
    Column("target_cover_days", Integer, nullable=False),
    Column("review_period_days", Integer, nullable=False),
    Column("service_level", Numeric(4, 3), nullable=False),
    Column("dead_stock_threshold_days", Integer, nullable=False),
)

variant_settings = Table(
    "variant_settings",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("brand_id", UUID(as_uuid=True), nullable=False),
    Column("variant_id", UUID(as_uuid=True), nullable=False),
    Column("lead_time_days", Integer),
    Column("target_cover_days", Integer),
    Column("cost_price", Numeric(10, 2)),
    Column("supplier_name", Text),
)

inventory_recommendations = Table(
    "inventory_recommendations",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("brand_id", UUID(as_uuid=True), nullable=False),
    Column("variant_id", UUID(as_uuid=True), nullable=False),
    Column("run_date", Date, nullable=False),
    Column("run_at", DateTime(timezone=True), nullable=False),
    Column("available", Integer, nullable=False),
    Column("lead_time_days", Integer, nullable=False),
    Column("target_cover_days", Integer, nullable=False),
    Column("review_period_days", Integer, nullable=False),
    Column("z_score", Numeric(6, 3), nullable=False),
    Column("in_stock_days_90d", Integer, nullable=False),
    Column("avg_daily_demand", Numeric(10, 4), nullable=False),
    Column("demand_std_daily", Numeric(10, 4), nullable=False),
    Column("days_cover", Numeric(10, 2)),
    Column("stockout_date", Date),
    Column("safety_stock", Numeric(10, 2), nullable=False),
    Column("reorder_point", Numeric(10, 2), nullable=False),
    Column("recommended_order_qty", Integer),
    Column("is_emergency_order", Boolean, nullable=False),
    Column("overstock_units", Integer),
    Column("excess_cover_days", Numeric(10, 2)),
    Column("dead_stock", Boolean, nullable=False),
    Column("risk_tier", Text, nullable=False),
    Column("recommended_action", Text, nullable=False),
    Column("revenue_at_risk", Numeric(12, 2)),
    Column("capital_trapped", Numeric(12, 2)),
    Column("created_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("variant_id", "run_date", name="uq_inv_rec_variant_date"),
)

# Read-only tables (only used for SELECT in the worker)
shopify_connections = Table(
    "shopify_connections",
    metadata,
    Column("brand_id", UUID(as_uuid=True), nullable=False),
    Column("shop_domain", Text, nullable=False),
    Column("access_token_enc", nullable=False),  # BYTEA — no SQLAlchemy type needed for reads
)

sync_runs = Table(
    "sync_runs",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("status", Text, nullable=False),
    Column("started_at", DateTime(timezone=True)),
    Column("finished_at", DateTime(timezone=True)),
    Column("error", Text),
    Column("entities", Text),  # JSONB — treated as text for raw SQL updates
)
