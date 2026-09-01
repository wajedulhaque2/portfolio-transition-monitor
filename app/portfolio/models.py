from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass(slots=True)
class Position:
    symbol: str
    quantity: float
    value_gbp: float
    average_price: float | None = None
    pnl_gbp: float | None = None
    current_price: float | None = None
    currency: str | None = None


@dataclass(slots=True)
class PortfolioState:
    total_value_gbp: float
    cash_gbp: float
    positions: list[Position]
    pending_buy_symbols: set[str] = field(default_factory=set)
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(slots=True)
class MarketMetrics:
    symbol: str
    current_price: float
    one_day_return: float
    five_day_return: float
    ten_day_return: float
    twenty_day_return: float
    pullback_from_20d_high: float
    rebound_from_20d_low: float
    atr14_pct: float
    realized_vol20: float
    data_fresh: bool = True
