from app.trading212.client import ALLOWED_GET_PATHS
from app.trading212.mapper import map_state


def test_only_get_paths_are_declared():
    assert all(p.startswith("/equity/") for p in ALLOWED_GET_PATHS)
    assert not any("market" in p or "limit" in p for p in ALLOWED_GET_PATHS)


def test_mapper_pending_order_and_unknown():
    s = map_state(
        {"total": 1000, "free": 100},
        [{"ticker": "NVDA_US_EQ", "quantity": 0.8, "currentPrice": 200, "currentValue": 160}],
        [{"ticker": "UBER_US_EQ", "side": "BUY", "status": "NEW"}],
        {"NVDA_US_EQ": "NVDA", "UBER_US_EQ": "UBER"},
    )
    assert s.positions[0].symbol == "NVDA"
    assert "UBER" in s.pending_buy_symbols
