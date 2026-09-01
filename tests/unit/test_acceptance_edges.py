from datetime import UTC, date, datetime, timedelta

import httpx
import pytest

from app.ai.arbiter import safe_decide
from app.ai.base import AIProvider
from app.config import get_portfolio_config, get_thresholds
from app.jobs.scan import MonitorEngine
from app.market_data.base import DailyBar, Quote
from app.portfolio.models import MarketMetrics, PortfolioState, Position
from app.signals.build import BuildSignal, build_score
from app.signals.metrics import _ret, atr14, compute_market_metrics, realized_vol20
from app.signals.rotation import rotation_score
from app.signals.trim import TrimSignal, trim_score
from app.utils_retry import retry_call


def metric(
    symbol="X",
    *,
    one=0.0,
    ten=0.0,
    twenty=0.0,
    pb=0.0,
    rebound=0.0,
    atr=0.03,
    fresh=True,
):
    return MarketMetrics(
        symbol=symbol,
        current_price=100.0,
        one_day_return=one,
        five_day_return=0.0,
        ten_day_return=ten,
        twenty_day_return=twenty,
        pullback_from_20d_high=pb,
        rebound_from_20d_low=rebound,
        atr14_pct=atr,
        realized_vol20=0.30,
        data_fresh=fresh,
    )


def test_build_signal_tiers_and_stale_fail_closed():
    thresholds = {
        "watch": 0.05,
        "strong": 0.10,
        "abnormal_day": 0.15,
    }

    stale = build_score(
        0.0,
        0.10,
        metric(pb=0.20, fresh=False),
        thresholds,
        1.0,
    )
    assert stale.tier == "IGNORE"

    weak = build_score(
        0.0,
        0.10,
        metric(pb=0.01),
        thresholds,
        1.0,
    )
    assert weak.tier == "IGNORE"

    strong = build_score(
        0.0,
        0.10,
        metric(pb=0.12, atr=0.03, one=-0.20),
        thresholds,
        1.0,
    )
    assert strong.tier == "STRONG"
    assert strong.manual_review is True

    review = build_score(
        0.0,
        0.10,
        metric(pb=0.10, atr=0.05),
        thresholds,
        0.0,
    )
    assert review.tier == "REVIEW"

    watch = build_score(
        0.0,
        0.10,
        metric(pb=0.10, atr=0.50),
        thresholds,
        0.20,
    )
    assert watch.tier == "WATCH"

    ignored = build_score(
        0.0,
        0.10,
        metric(pb=0.10, atr=0.50),
        thresholds,
        0.0,
    )
    assert ignored.tier == "IGNORE"


def test_trim_signal_tiers_are_symbol_agnostic():
    thresholds = {
        "watch": 0.05,
        "strong": 0.10,
    }

    stale = trim_score(
        0.20,
        0.10,
        metric("ANY", rebound=0.20, fresh=False),
        thresholds,
        1.0,
    )
    assert stale.tier == "IGNORE"

    weak = trim_score(
        0.20,
        0.10,
        metric("ANY", rebound=0.01),
        thresholds,
        1.0,
    )
    assert weak.tier == "IGNORE"

    strong = trim_score(
        0.20,
        0.10,
        metric("ANY", rebound=0.10),
        thresholds,
        1.0,
        pnl_gbp=100,
    )
    assert strong.tier == "STRONG"

    review = trim_score(
        0.20,
        0.10,
        metric("ANY", rebound=0.10),
        thresholds,
        0.25,
    )
    assert review.tier == "REVIEW"

    watch = trim_score(
        0.20,
        0.10,
        metric("ANY", rebound=0.10),
        thresholds,
        0.0,
    )
    assert watch.tier == "WATCH"

    ignored = trim_score(
        0.11,
        0.10,
        metric("ANY", rebound=0.10),
        thresholds,
        0.0,
    )
    assert ignored.tier == "IGNORE"


def test_rotation_all_tiers_and_bonus_clamping():
    strong = rotation_score(
        TrimSignal("AAPL", 100, "STRONG"),
        BuildSignal("GOOGL", 100, "STRONG"),
        0.50,
    )
    assert strong.tier == "STRONG"
    assert strong.score == 100.0

    review = rotation_score(
        TrimSignal("AAPL", 80, "REVIEW"),
        BuildSignal("GOOGL", 80, "REVIEW"),
        0.10,
    )
    assert review.tier == "REVIEW"

    watch = rotation_score(
        TrimSignal("AAPL", 70, "WATCH"),
        BuildSignal("GOOGL", 70, "WATCH"),
        0.10,
    )
    assert watch.tier == "WATCH"

    ignored = rotation_score(
        TrimSignal("AAPL", 50, "IGNORE"),
        BuildSignal("GOOGL", 50, "IGNORE"),
        -1.0,
    )
    assert ignored.tier == "IGNORE"


def make_bars(n=30):
    start = date(2026, 1, 1)
    result = []

    for i in range(n):
        close = 100.0 + i

        result.append(
            DailyBar(
                start + timedelta(days=i),
                close - 1,
                close + 1,
                close - 2,
                close,
            )
        )

    return result


def test_metric_edge_cases():
    assert _ret(10.0, 0.0) == 0.0
    assert atr14([]) == 0.0

    zero_bars = [
        DailyBar(
            date(2026, 1, i + 1),
            0,
            0,
            0,
            0,
        )
        for i in range(3)
    ]

    assert realized_vol20(zero_bars) == 0.0

    with pytest.raises(
        ValueError,
        match="at least 21",
    ):
        compute_market_metrics(
            "X",
            Quote(
                "X",
                100.0,
                datetime.now(UTC),
            ),
            make_bars(20),
        )

    with pytest.raises(
        ValueError,
        match="current price must be positive",
    ):
        compute_market_metrics(
            "X",
            Quote(
                "X",
                0.0,
                datetime.now(UTC),
            ),
            make_bars(),
        )


def test_engine_rejects_stale_buy_signal():
    engine = MonitorEngine(
        get_portfolio_config(),
        get_thresholds(),
    )

    state = PortfolioState(
        total_value_gbp=10000,
        cash_gbp=1000,
        positions=[
            Position(
                symbol="GOOGL",
                quantity=1,
                value_gbp=500,
                pnl_gbp=0,
            )
        ],
    )

    stale = metric(
        "GOOGL",
        pb=0.20,
        atr=0.03,
        fresh=False,
    )

    assert engine.evaluate(
        state,
        {"GOOGL": stale},
    ) == []


class TimeoutAI(AIProvider):
    def decide(self, payload):
        raise httpx.ReadTimeout(
            "synthetic timeout"
        )


def test_ai_timeout_fails_closed():
    decision = safe_decide(
        TimeoutAI(),
        {},
        max_amount=100,
    )

    assert decision.decision == "NO_ACTION"
    assert decision.action_type == "HOLD"
    assert decision.amount_gbp == 0
    assert decision.confidence == 0


def test_429_retry_is_bounded(monkeypatch):
    attempts = 0
    sleeps = []

    def fail_with_429():
        nonlocal attempts
        attempts += 1

        response = httpx.Response(
            429,
            request=httpx.Request(
                "GET",
                "https://example.test/rate-limit",
            ),
        )

        response.raise_for_status()

    monkeypatch.setattr(
        "app.utils_retry.time.sleep",
        sleeps.append,
    )

    with pytest.raises(
        httpx.HTTPStatusError,
    ):
        retry_call(
            fail_with_429,
            attempts=3,
            base_delay=0.5,
        )

    assert attempts == 3
    assert sleeps == [0.5, 1.0]
