from __future__ import annotations

from typing import Any

from app.portfolio.models import PortfolioState, Position


def _first(d: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return default


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def map_state(
    summary: Any, positions: Any, orders: Any, ticker_map: dict[str, str]
) -> PortfolioState:
    """Map current Trading 212 v0 responses into the monitor's account-currency state.

    Current API shapes are nested:
      summary.cash.availableToTrade
      summary.totalValue
      position.instrument.ticker
      position.walletImpact.currentValue / unrealizedProfitLoss / currency

    A few legacy aliases remain accepted defensively because the Public API is beta.
    """
    s = _dict(summary)
    cash_obj = _dict(s.get("cash"))
    investments = _dict(s.get("investments"))

    cash_raw = _first(
        cash_obj,
        "availableToTrade",
        "free",
        "availableCash",
        default=None,
    )
    if cash_raw is None:
        cash_raw = _first(s, "free", "freeCash", "availableCash", default=0.0)
    cash = float(cash_raw or 0.0)

    total_raw = _first(s, "totalValue", "total", "portfolioValue", "equity", default=None)
    if total_raw is None:
        current_investments = _first(investments, "currentValue", "totalValue", default=0.0)
        total_raw = cash + float(current_investments or 0.0)
    total = float(total_raw or 0.0)

    out: list[Position] = []
    for raw in positions or []:
        if not isinstance(raw, dict):
            continue
        instrument = _dict(raw.get("instrument"))
        wallet = _dict(raw.get("walletImpact"))
        broker_ticker = str(
            _first(raw, "ticker", "instrumentCode", default=None)
            or _first(instrument, "ticker", default="UNKNOWN")
        )
        sym = ticker_map.get(broker_ticker, broker_ticker)
        qty = float(_first(raw, "quantity", "qty", default=0.0) or 0.0)
        current = _first(raw, "currentPrice", "price", default=None)
        avg = _first(raw, "averagePricePaid", "averagePrice", "avgPrice", default=None)
        pnl = _first(wallet, "unrealizedProfitLoss", default=None)
        if pnl is None:
            pnl = _first(raw, "ppl", "pnl", "profitLoss", default=None)
        value = _first(wallet, "currentValue", default=None)
        if value is None:
            value = _first(raw, "currentValue", "value", "marketValue", default=None)
        # Only fall back to qty*current for same-currency/legacy responses. Current T212
        # walletImpact.currentValue is preferred because it is in the account currency.
        if value is None and current is not None:
            value = qty * float(current)
        currency = (
            _first(wallet, "currency", default=None)
            or _first(instrument, "currency", "currencyCode", default=None)
            or _first(raw, "currency", default=None)
        )
        out.append(
            Position(
                sym,
                qty,
                float(value or 0.0),
                None if avg is None else float(avg),
                None if pnl is None else float(pnl),
                None if current is None else float(current),
                None if currency is None else str(currency),
            )
        )

    if total <= 0:
        total = cash + sum(p.value_gbp for p in out)

    pending: set[str] = set()
    terminal = {"FILLED", "CANCELLED", "CANCELED", "REJECTED", "EXPIRED"}
    for order in orders or []:
        if not isinstance(order, dict):
            continue
        instrument = _dict(order.get("instrument"))
        side = str(_first(order, "side", default="")).upper()
        status = str(_first(order, "status", default="")).upper()
        if side == "BUY" and status not in terminal:
            broker_ticker = str(
                _first(order, "ticker", "instrumentCode", default=None)
                or _first(instrument, "ticker", default="")
            )
            if broker_ticker:
                pending.add(ticker_map.get(broker_ticker, broker_ticker))
    return PortfolioState(total, cash, out, pending)
