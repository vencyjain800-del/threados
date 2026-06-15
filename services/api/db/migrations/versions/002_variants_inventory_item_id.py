"""Add inventory_item_id column to variants

Revision ID: 002
Revises: 001
Create Date: 2026-06-11

Rationale
---------
The ``inventory_item_id`` field returned by the Shopify Products API links a
variant to its inventory tracking record.  Without this column the worker cannot
resolve ``inventory_levels/update`` webhook payloads (which carry only
``inventory_item_id``) to an internal variant UUID — so webhook-based inventory
sync has been a no-op since Sprint 2.

This migration adds the column (nullable) and a composite index for fast lookups
by ``(brand_id, inventory_item_id)``.  Existing rows have ``NULL``; the column is
backfilled during the next full backfill or incremental sync for each brand.

Safety
------
* ADD COLUMN ... NULL acquires only a brief AccessShareLock on PostgreSQL 15+.
* No downtime required — the column is additive and nullable.
* The worker upsert is updated to write ``inventory_item_id`` on every sync,
  so the column is progressively populated without a bulk UPDATE.
"""
import sqlalchemy as sa
from alembic import op

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "variants",
        sa.Column("inventory_item_id", sa.BigInteger, nullable=True),
    )
    # Composite index: brand_id scopes the lookup to the current tenant;
    # inventory_item_id is the search key for webhook resolution.
    op.create_index(
        "ix_variants_inventory_item_id",
        "variants",
        ["brand_id", "inventory_item_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_variants_inventory_item_id", table_name="variants")
    op.drop_column("variants", "inventory_item_id")
