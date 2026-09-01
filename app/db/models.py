from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
)


class Base(DeclarativeBase):
    pass


def now() -> datetime:
    return datetime.now(UTC)


class ScanRun(Base):
    __tablename__ = "scan_runs"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    scan_id: Mapped[str] = mapped_column(
        String(64),
        unique=True,
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=now,
    )

    finished_at: Mapped[
        datetime | None
    ] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(32),
        default="running",
    )

    candidate_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    notification_sent: Mapped[
        bool
    ] = mapped_column(
        Boolean,
        default=False,
    )

    detail: Mapped[str] = mapped_column(
        Text,
        default="",
    )


class PortfolioSnapshot(Base):
    __tablename__ = "portfolio_snapshots"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=now,
    )

    total_value_gbp: Mapped[
        float
    ] = mapped_column(
        Float,
    )

    cash_gbp: Mapped[float] = mapped_column(
        Float,
    )


class PositionSnapshot(Base):
    __tablename__ = "position_snapshots"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=now,
    )

    symbol: Mapped[str] = mapped_column(
        String(32),
    )

    quantity: Mapped[float] = mapped_column(
        Float,
    )

    value_gbp: Mapped[float] = mapped_column(
        Float,
    )

    average_price: Mapped[
        float | None
    ] = mapped_column(
        Float,
        nullable=True,
    )

    pnl_gbp: Mapped[
        float | None
    ] = mapped_column(
        Float,
        nullable=True,
    )


class AlertRecord(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=now,
    )

    fingerprint: Mapped[str] = mapped_column(
        String(128),
        index=True,
    )

    tier: Mapped[str] = mapped_column(
        String(32),
    )

    message: Mapped[str] = mapped_column(
        Text,
    )


class LockRecord(Base):
    __tablename__ = "locks"

    name: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
    )

    acquired_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=now,
    )


class MarketHistoryCacheRecord(Base):
    __tablename__ = "market_history_cache"

    __table_args__ = (
        UniqueConstraint(
            "source",
            "symbol",
            name=(
                "uq_market_history_"
                "source_symbol"
            ),
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    source: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    symbol: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=now,
        nullable=False,
    )

    latest_bar_date: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
    )

    payload: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )


class ProviderHealthRecord(Base):
    __tablename__ = "provider_health"

    provider: Mapped[str] = mapped_column(
        String(32),
        primary_key=True,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=now,
        nullable=False,
    )

    last_success_at: Mapped[
        datetime | None
    ] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    last_failure_at: Mapped[
        datetime | None
    ] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    last_operation: Mapped[str] = mapped_column(
        String(128),
        default="",
        nullable=False,
    )

    consecutive_failures: Mapped[
        int
    ] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    total_successes: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    total_failures: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    last_error: Mapped[str] = mapped_column(
        String(128),
        default="",
        nullable=False,
    )