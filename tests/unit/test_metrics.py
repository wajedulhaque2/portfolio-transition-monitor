from datetime import UTC, date, datetime, timedelta

from app.market_data.base import DailyBar, Quote
from app.signals.metrics import atr14, compute_market_metrics


def bars(n=30, start=100.0):
    d = date(2026, 1, 1)
    out = []
    for i in range(n):
        c = start + i
        out.append(DailyBar(d + timedelta(days=i), c - 1, c + 1, c - 2, c))
    return out


def test_metrics():
    b = bars()
    q = Quote("X", 125, datetime.now(UTC))
    m = compute_market_metrics("X", q, b)
    assert m.current_price == 125
    assert m.pullback_from_20d_high > 0
    assert atr14(b) > 0
