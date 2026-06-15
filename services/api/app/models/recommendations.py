"""ORM models for the inventory intelligence tables — Sprint 3."""
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class InventorySettings(Base):
    """Brand-level inventory policy defaults."""

    __tablename__ = "inventory_settings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("brands.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    default_lead_time: Mapped[int] = mapped_column(Integer, nullable=False, default=14)
    target_cover_days: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    review_period_days: Mapped[int] = mapped_column(Integer, nullable=False, default=7)
    service_level: Mapped[Decimal] = mapped_column(
        Numeric(4, 3), nullable=False, default=Decimal("0.950")
    )
    dead_stock_threshold_days: Mapped[int] = mapped_column(
        Integer, nullable=False, default=90
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(tz=UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(tz=UTC)
    )


class VariantSettings(Base):
    """Per-SKU overrides of brand inventory policy defaults."""

    __tablename__ = "variant_settings"
    __table_args__ = (
        UniqueConstraint("brand_id", "variant_id", name="uq_variant_settings_variant"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("brands.id", ondelete="CASCADE"),
        nullable=False,
    )
    variant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("variants.id", ondelete="CASCADE"),
        nullable=False,
    )
    lead_time_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    target_cover_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    supplier_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(tz=UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(tz=UTC)
    )


class InventoryRecommendation(Base):
    """Computed inventory intelligence per variant per run_date."""

    __tablename__ = "inventory_recommendations"
    __table_args__ = (
        UniqueConstraint("variant_id", "run_date", name="uq_inv_rec_variant_date"),
        CheckConstraint(
            "risk_tier IN ('stockout','reorder','healthy','overstock','dead')",
            name="chk_inv_rec_risk_tier",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("brands.id", ondelete="CASCADE"),
        nullable=False,
    )
    variant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("variants.id", ondelete="CASCADE"),
        nullable=False,
    )
    run_date: Mapped[date] = mapped_column(Date, nullable=False)
    run_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(tz=UTC)
    )

    # Inputs
    available: Mapped[int] = mapped_column(Integer, nullable=False)
    lead_time_days: Mapped[int] = mapped_column(Integer, nullable=False)
    target_cover_days: Mapped[int] = mapped_column(Integer, nullable=False)
    review_period_days: Mapped[int] = mapped_column(Integer, nullable=False)
    z_score: Mapped[Decimal] = mapped_column(Numeric(6, 3), nullable=False)
    in_stock_days_90d: Mapped[int] = mapped_column(Integer, nullable=False)

    # Demand model
    avg_daily_demand: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    demand_std_daily: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)

    # Computed outputs
    days_cover: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    stockout_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    safety_stock: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    reorder_point: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    recommended_order_qty: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_emergency_order: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    overstock_units: Mapped[int | None] = mapped_column(Integer, nullable=True)
    excess_cover_days: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2), nullable=True
    )
    dead_stock: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Classification
    risk_tier: Mapped[str] = mapped_column(Text, nullable=False)
    recommended_action: Mapped[str] = mapped_column(Text, nullable=False)

    # Value metrics
    revenue_at_risk: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2), nullable=True
    )
    capital_trapped: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(tz=UTC)
    )
