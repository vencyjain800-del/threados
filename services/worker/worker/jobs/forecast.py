"""
Forecasting jobs — Sprint 3.

Stubs only. Full implementation: Sprint 3 (ML forecasting).
"""
import structlog

log = structlog.get_logger()


def run_forecast(brand_id: str) -> None:
    """Run nightly demand forecast for all active SKUs of a brand."""
    log.info("forecast.run.stub", brand_id=brand_id)
    raise NotImplementedError("Forecasting job is implemented in Sprint 3")
