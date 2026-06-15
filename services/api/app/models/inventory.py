import uuid
from datetime import UTC, date, datetime

from sqlalchemy import BigInteger, Boolean, Date, DateTime, ForeignKey, Integer, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class InventoryLevel(Base):
    __tablename__ = "inventory_levels"

    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id", ondelete="CASCADE"), nullable=False
    )
    variant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("variants.id", ondelete="CASCADE"), primary_key=True
    )
    location_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    available: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(tz=UTC)
    )


class InventorySnapshot(Base):
    __tablename__ = "inventory_snapshots"

    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id", ondelete="CASCADE"), nullable=False
    )
    variant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("variants.id", ondelete="CASCADE"), primary_key=True
    )
    snap_date: Mapped[date] = mapped_column(Date, primary_key=True)
    available: Mapped[int] = mapped_column(Integer, nullable=False)


class SalesDaily(Base):
    """Aggregated daily sales per variant. Populated by the sync worker (Sprint 2)."""

    __tablename__ = "sales_daily"

    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id", ondelete="CASCADE"), nullable=False
    )
    variant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("variants.id", ondelete="CASCADE"), primary_key=True
    )
    sale_date: Mapped[date] = mapped_column(Date, primary_key=True)
    units_sold: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    gross_revenue: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    avg_discount: Mapped[float] = mapped_column(Numeric(6, 4), nullable=False, default=0)
    was_in_stock: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    was_on_promo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
