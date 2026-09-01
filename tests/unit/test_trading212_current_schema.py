from app.trading212.mapper import map_state


def test_current_api_nested_schema_maps_account_currency_values():
    summary = {
        "cash": {"availableToTrade": 140.0, "inPies": 0.0, "reservedForOrders": 10.0},
        "currency": "GBP",
        "investments": {"currentValue": 12333.0, "unrealizedProfitLoss": 123.0},
        "totalValue": 12473.0,
    }
    positions = [
        {
            "averagePricePaid": 180.0,
            "currentPrice": 208.0,
            "instrument": {"ticker": "NVDA_US_EQ", "name": "NVIDIA", "currency": "USD"},
            "quantity": 0.8,
            "walletImpact": {
                "currency": "GBP",
                "currentValue": 132.10,
                "totalCost": 120.0,
                "unrealizedProfitLoss": 12.10,
                "fxImpact": 1.0,
            },
        }
    ]
    orders = [
        {
            "ticker": "UBER_US_EQ",
            "instrument": {"ticker": "UBER_US_EQ"},
            "side": "BUY",
            "status": "NEW",
        }
    ]
    state = map_state(summary, positions, orders, {"NVDA_US_EQ": "NVDA", "UBER_US_EQ": "UBER"})
    assert state.cash_gbp == 140.0
    assert state.total_value_gbp == 12473.0
    assert state.positions[0].symbol == "NVDA"
    assert state.positions[0].value_gbp == 132.10
    assert state.positions[0].pnl_gbp == 12.10
    assert state.positions[0].average_price == 180.0
    assert "UBER" in state.pending_buy_symbols
