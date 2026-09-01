from app.jobs.scan import Recommendation, format_alert
from app.portfolio.models import MarketMetrics, PortfolioState


def market_metric(
    symbol: str,
    *,
    price: float = 100.0,
    pullback: float = 0.0,
    rebound: float = 0.0,
) -> MarketMetrics:
    return MarketMetrics(
        symbol=symbol,
        current_price=price,
        one_day_return=0.0,
        five_day_return=0.0,
        ten_day_return=0.0,
        twenty_day_return=0.0,
        pullback_from_20d_high=pullback,
        rebound_from_20d_low=rebound,
        atr14_pct=0.03,
        realized_vol20=0.30,
        data_fresh=True,
    )


def portfolio() -> PortfolioState:
    return PortfolioState(
        total_value_gbp=10000,
        cash_gbp=250,
        positions=[],
    )


def test_format_rotate_alert():
    recommendation = Recommendation(
        action="ROTATE",
        buy_symbol="GOOGL",
        sell_symbol="AAPL",
        amount_gbp=100,
        score=90,
        tier="STRONG",
        reason="Rotate strength into pullback",
    )

    metrics = {
        "GOOGL": market_metric(
            "GOOGL",
            price=80,
            pullback=0.10,
        ),
        "AAPL": market_metric(
            "AAPL",
            price=120,
            rebound=0.08,
        ),
    }

    message = format_alert(
        recommendation,
        portfolio(),
        metrics,
        dry_run=True,
    )

    assert "ROTATE: £100 AAPL → GOOGL" in message
    assert "GOOGL: 80.00, pullback 10.0% from 20d high" in message
    assert "AAPL: rebound 8.0% from 20d low" in message
    assert "Score: 90.0 (STRONG)" in message
    assert "Cash: ~£250" in message
    assert "Advisory only — no automatic trade has been placed." in message


def test_format_trim_alert():
    recommendation = Recommendation(
        action="TRIM",
        buy_symbol=None,
        sell_symbol="AAPL",
        amount_gbp=75,
        score=80,
        tier="REVIEW",
        reason="Overweight and strong",
    )

    metrics = {
        "AAPL": market_metric(
            "AAPL",
            rebound=0.06,
        ),
    }

    message = format_alert(
        recommendation,
        portfolio(),
        metrics,
        dry_run=False,
    )

    assert "TRIM: ~£75 AAPL" in message
    assert "AAPL: rebound 6.0% from 20d low" in message
    assert "Advisory only" not in message


def test_format_buy_alert():
    recommendation = Recommendation(
        action="BUY",
        buy_symbol="GOOGL",
        sell_symbol=None,
        amount_gbp=50,
        score=78,
        tier="REVIEW",
        reason="Pullback while underweight",
    )

    metrics = {
        "GOOGL": market_metric(
            "GOOGL",
            price=90,
            pullback=0.08,
        ),
    }

    message = format_alert(
        recommendation,
        portfolio(),
        metrics,
        dry_run=True,
    )

    assert "BUY/ADD: ~£50 GOOGL" in message
    assert "GOOGL: 90.00, pullback 8.0% from 20d high" in message


def test_format_manual_review_alert():
    recommendation = Recommendation(
        action="MANUAL_REVIEW",
        buy_symbol="GOOGL",
        sell_symbol=None,
        amount_gbp=0,
        score=88,
        tier="STRONG",
        reason="Abnormal one-day drop",
        manual_review=True,
    )

    message = format_alert(
        recommendation,
        portfolio(),
        {},
        dry_run=True,
    )

    assert "MANUAL REVIEW: GOOGL" in message
    assert "Large pullback detected: verify the reason before adding." in message
    assert "Advisory only — no automatic trade has been placed." in message
