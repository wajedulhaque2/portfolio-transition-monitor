from app.config import get_portfolio_config, get_thresholds
from app.jobs.scan import MonitorEngine
from app.portfolio.models import MarketMetrics, PortfolioState, Position


def mm(sym, one=0, ten=0, twenty=0, pb=0, rebound=0, atr=0.03):
    return MarketMetrics(sym, 100, one, 0, ten, twenty, pb, rebound, atr, 0.3, True)


def state_with(weights, total=10000, cash=1000):
    positions = []
    for sym, weight in weights.items():
        if sym != "CASH":
            positions.append(Position(sym, 1, total * weight, pnl_gbp=100))
    return PortfolioState(total, cash, positions)


def test_aapl_to_googl_rotation():
    engine = MonitorEngine(get_portfolio_config(), get_thresholds())
    state = state_with({"AAPL": 0.40, "GOOGL": 0.05, "CASH": 0.10})
    metrics = {
        "AAPL": mm("AAPL", ten=0.15, twenty=0.15, rebound=0.15),
        "GOOGL": mm("GOOGL", pb=0.10, atr=0.025),
    }

    recommendations = engine.evaluate(state, metrics)

    assert any(
        rec.action == "ROTATE"
        and rec.sell_symbol == "AAPL"
        and rec.buy_symbol == "GOOGL"
        for rec in recommendations
    )


def test_amzn_small_pullback_no_action():
    engine = MonitorEngine(get_portfolio_config(), get_thresholds())
    state = state_with({"AMZN": 0.05, "CASH": 0.10})

    assert engine.evaluate(
        state,
        {"AMZN": mm("AMZN", pb=0.02, atr=0.02)},
    ) == []


def test_msft_rebound_trim():
    engine = MonitorEngine(get_portfolio_config(), get_thresholds())
    state = state_with({"MSFT": 0.45, "CASH": 0.10})

    recommendations = engine.evaluate(
        state,
        {"MSFT": mm("MSFT", ten=0.15, twenty=0.15, rebound=0.15)},
    )

    assert any(
        rec.action == "TRIM" and rec.sell_symbol == "MSFT"
        for rec in recommendations
    )


def test_googl_abnormal_drop_manual_review():
    engine = MonitorEngine(get_portfolio_config(), get_thresholds())
    state = state_with({"GOOGL": 0.05, "CASH": 0.10})

    recommendations = engine.evaluate(
        state,
        {"GOOGL": mm("GOOGL", one=-0.15, pb=0.15, atr=0.04)},
    )

    assert any(rec.action == "MANUAL_REVIEW" for rec in recommendations)


def test_pending_googl_suppresses_build():
    engine = MonitorEngine(get_portfolio_config(), get_thresholds())
    state = state_with({"GOOGL": 0.05, "CASH": 0.10})
    state.pending_buy_symbols = {"GOOGL"}

    assert engine.evaluate(
        state,
        {"GOOGL": mm("GOOGL", pb=0.12, atr=0.03)},
    ) == []
