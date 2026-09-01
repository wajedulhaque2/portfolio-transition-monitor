from __future__ import annotations

import math

from app.market_data.base import DailyBar, Quote
from app.portfolio.models import MarketMetrics


def _ret(a: float, b: float) -> float:
    return 0.0 if b == 0 else a / b - 1.0


def atr14(bars: list[DailyBar]) -> float:
    if len(bars) < 15:
        return 0.0

    trs: list[float] = []

    for prev, cur in zip(bars[-15:-1], bars[-14:]):
        trs.append(
            max(
                cur.high - cur.low,
                abs(cur.high - prev.close),
                abs(cur.low - prev.close),
            )
        )

    return sum(trs) / len(trs)


def realized_vol20(bars: list[DailyBar]) -> float:
    closes = [b.close for b in bars[-21:]]

    if len(closes) < 3:
        return 0.0

    rs = [
        math.log(closes[i] / closes[i - 1])
        for i in range(1, len(closes))
        if closes[i - 1] > 0 and closes[i] > 0
    ]

    if len(rs) < 2:
        return 0.0

    mean = sum(rs) / len(rs)
    var = sum((x - mean) ** 2 for x in rs) / (len(rs) - 1)

    return math.sqrt(var) * math.sqrt(252)


def compute_market_metrics(
    symbol: str,
    quote: Quote,
    bars: list[DailyBar],
    fresh: bool = True,
) -> MarketMetrics:
    if len(bars) < 21:
        raise ValueError("need at least 21 daily bars")

    closes = [b.close for b in bars]
    current = quote.price

    if current <= 0:
        raise ValueError("current price must be positive")

    prev = closes[-1]

    high20 = max([b.high for b in bars[-20:]] + [current])
    low20 = min([b.low for b in bars[-20:]] + [current])

    if high20 <= 0 or low20 <= 0:
        raise ValueError("20-day price range must be positive")

    atr = atr14(bars)

    return MarketMetrics(
        symbol=symbol,
        current_price=current,
        one_day_return=_ret(current, prev),
        five_day_return=_ret(current, closes[-5]),
        ten_day_return=_ret(current, closes[-10]),
        twenty_day_return=_ret(current, closes[-20]),
        pullback_from_20d_high=max(
            0.0,
            1.0 - current / high20,
        ),
        rebound_from_20d_low=max(
            0.0,
            current / low20 - 1.0,
        ),
        atr14_pct=atr / current,
        realized_vol20=realized_vol20(bars),
        data_fresh=fresh,
    )
