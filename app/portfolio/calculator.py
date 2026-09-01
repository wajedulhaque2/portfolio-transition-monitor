from __future__ import annotations

from app.portfolio.models import PortfolioState


def weights(state: PortfolioState, groups: dict[str, list[str]] | None = None) -> dict[str, float]:
    total = state.total_value_gbp
    if total <= 0:
        return {"CASH": 0.0}
    out = {p.symbol: p.value_gbp / total for p in state.positions}
    out["CASH"] = state.cash_gbp / total
    for group, members in (groups or {}).items():
        out[group] = sum(out.get(m, 0.0) for m in members)
    return out


def gbx_to_gbp(value_gbx: float) -> float:
    return value_gbx / 100.0


def usd_to_gbp(value_usd: float, gbp_per_usd: float) -> float:
    return value_usd * gbp_per_usd
