from __future__ import annotations

from dataclasses import dataclass

from app.portfolio.models import MarketMetrics


@dataclass(slots=True)
class TrimSignal:
    symbol: str
    score: float
    tier: str


def trim_score(
    current_weight: float,
    target_weight: float,
    metrics: MarketMetrics,
    thresholds: dict,
    priority: float,
    pnl_gbp: float | None = None,
) -> TrimSignal:
    """Score a generic trim candidate.

    Symbol-specific investment preferences belong in configuration, not in
    application code. A symbol is eligible only when it is above target, its
    market data is fresh, and its measured strength clears the configured
    watch threshold.

    A zero target is valid and represents a gradual transition out of a
    position. In that case the position is treated as fully overweight rather
    than dividing by a zero target.
    """
    if target_weight < 0 or current_weight <= target_weight or not metrics.data_fresh:
        return TrimSignal(metrics.symbol, 0.0, "IGNORE")

    strength_raw = max(
        metrics.rebound_from_20d_low,
        max(0.0, metrics.ten_day_return),
        max(0.0, metrics.twenty_day_return),
    )
    if strength_raw < thresholds["watch"]:
        return TrimSignal(metrics.symbol, 0.0, "IGNORE")

    if target_weight == 0:
        over = 1.0
    else:
        over = min(1.0, (current_weight - target_weight) / target_weight)

    strength = min(1.0, strength_raw / max(thresholds["strong"], 1e-9))
    pnl_bonus = 1.0 if (pnl_gbp or 0.0) > 0 else 0.0
    score = 100 * (0.40 * over + 0.30 * strength + 0.20 * priority + 0.10 * pnl_bonus)

    if score >= 85:
        tier = "STRONG"
    elif score >= 75:
        tier = "REVIEW"
    elif score >= 65:
        tier = "WATCH"
    else:
        tier = "IGNORE"

    return TrimSignal(metrics.symbol, round(score, 2), tier)
