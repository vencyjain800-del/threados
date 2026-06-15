"""ORM model for the forecasts table — Sprint 3 Phase D."""
import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Index, Numeric, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Forecast(Base):
    """Per-variant daily demand forecast produced by the nightly worker job.

    Primary key is the surrogate ``id``.  The logical unique key is
    ``(variant_id, forecast_date, run_date)`` — one prediction per horizon
    date per job run, allowing multiple model runs to coexist while the
    worker upserts (not inserts) on conflict.
    """

    __tablename__ = "forecasts"
    __table_args__ = (
        UniqueConstraint(
            "variant_id",
            "forecast_date",
            "run_date",
            name="uq_forecasts_variant_date_run",
        ),
        Index("ix_forecasts_brand_run", "brand_id", "run_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id", ondelete="CASCADE"), nullable=False
    )
    variant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("variants.id", ondelete="CASCADE"), nullable=False
    )
    forecast_date: Mapped[date] = mapped_column(Date, nullable=False)
    run_date: Mapped[date] = mapped_column(Date, nullable=False)
    predicted_units: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    lower_bound: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    upper_bound: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    model_name: Mapped[str] = mapped_column(Text, nullable=False)
