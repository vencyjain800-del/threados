"""
Minimal SQLAlchemy Core Table definitions for the worker.

These are NOT ORM models — just enough column metadata to enable
``pg_insert().on_conflict_do_update().returning()`` without importing
anything from services/api.

Only columns that are actively read or written by the worker are declared.
"""
from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    Integer,
    MetaData,
    Numeric,
    Table,
    Text,
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
