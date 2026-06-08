"""
Shopify sync jobs — Sprint 2.

Stubs registered here so the worker can import them cleanly.
Full implementation: Sprint 2 (Shopify data ingestion).
"""
import structlog

log = structlog.get_logger()


def run_backfill(brand_id: str, sync_run_id: str) -> None:
    """Full historical backfill of orders, products, and inventory from Shopify."""
    log.info("sync.backfill.stub", brand_id=brand_id, sync_run_id=sync_run_id)
    raise NotImplementedError("Shopify backfill job is implemented in Sprint 2")


def run_incremental(brand_id: str, sync_run_id: str) -> None:
    """Incremental sync — pull changes since last successful run."""
    log.info("sync.incremental.stub", brand_id=brand_id, sync_run_id=sync_run_id)
    raise NotImplementedError("Shopify incremental sync is implemented in Sprint 2")
