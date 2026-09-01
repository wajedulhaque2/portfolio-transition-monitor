from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime


@dataclass(slots=True)
class Quote:
    symbol: str
    price: float
    timestamp: datetime
    currency: str = "USD"


@dataclass(slots=True)
class DailyBar:
    date: date
    open: float
    high: float
    low: float
    close: float


class MarketDataProvider(ABC):
    @abstractmethod
    def quote(self, symbol: str) -> Quote: ...

    @abstractmethod
    def history(self, symbol: str, outputsize: int = 260) -> list[DailyBar]: ...
