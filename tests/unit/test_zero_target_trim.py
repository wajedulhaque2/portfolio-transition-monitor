from app.jobs.scan import MonitorEngine
from app.portfolio.models import MarketMetrics, PortfolioState, Position
from app.signals.trim import trim_score


def strong_metric(symbol: str) -> MarketMetrics:
    return MarketMetrics(
        symbol=symbol,
        current_price=100.0,
        one_day_return=0.01,
        five_day_return=0.05,
        ten_day_return=0.15,
        twenty_day_return=0.20,
        pullback_from_20d_high=0.0,
        rebound_from_20d_low=0.20,
        atr14_pct=0.03,
        realized_vol20=0.30,
        data_fresh=True,
    )


def test_trim_score_supports_zero_target():
    signal = trim_score(
        current_weight=0.20,
        target_weight=0.0,
        metrics=strong_metric("EXITME"),
        thresholds={
            "watch": 0.05,
            "review": 0.10,
            "strong": 0.15,
        },
        priority=1.0,
        pnl_gbp=100.0,
    )

    assert signal.tier == "STRONG"
    assert signal.score == 100.0


def test_engine_can_gradually_trim_position_to_zero_target():
    config = {
        "hard_min_cash_gbp": 100,
        "max_single_transition_pct": 0.015,
        "targets": {
            "EXITME": 0.0,
            "KEEP": 0.90,
            "CASH": 0.10,
        },
        "groups": {},
        "soft_component_targets": {},
        "strategic_priority": {
            "EXITME": 1.0,
        },
    }
    thresholds = {
        "pullback": {},
        "trim": {
            "EXITME": {
                "watch": 0.05,
                "review": 0.10,
                "strong": 0.15,
            }
        },
    }
    state = PortfolioState(
        total_value_gbp=10000,
        cash_gbp=1000,
        positions=[
            Position(
                symbol="EXITME",
                quantity=20,
                value_gbp=2000,
                pnl_gbp=100,
            )
        ],
    )

    recommendations = MonitorEngine(config, thresholds).evaluate(
        state,
        {"EXITME": strong_metric("EXITME")},
    )

    trims = [
        recommendation
        for recommendation in recommendations
        if recommendation.action == "TRIM" and recommendation.sell_symbol == "EXITME"
    ]

    assert trims
    assert trims[0].amount_gbp > 0
