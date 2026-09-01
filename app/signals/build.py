from __future__ import annotations

from dataclasses import dataclass

from app.portfolio.models import MarketMetrics


@dataclass(slots=True)
class BuildSignal:
    symbol: str
    score: float
    tier: str
    manual_review: bool = False


def build_score(
    current_weight: float,
    target_weight: float,
    metrics: MarketMetrics,
    thresholds: dict,
    priority: float,
) -> BuildSignal:
    if target_weight <= 0 or current_weight >= target_weight or not metrics.data_fresh:
        return BuildSignal(metrics.symbol, 0.0, "IGNORE")
    pb = metrics.pullback_from_20d_high
    if pb < thresholds["watch"]:
        return BuildSignal(metrics.symbol, 0.0, "IGNORE")
    under = min(1.0, max(0.0, (target_weight - current_weight) / target_weight))
    raw = min(1.0, pb / max(thresholds["strong"], 1e-9))
    atr_sig = min(1.0, pb / max(2 * metrics.atr14_pct, 0.01))
    score = 100 * (0.30 * under + 0.30 * raw + 0.20 * atr_sig + 0.20 * priority)
    if score >= 85:
        tier = "STRONG"
    elif score >= 75:
        tier = "REVIEW"
    elif score >= 65:
        tier = "WATCH"
    else:
        tier = "IGNORE"
    manual = metrics.one_day_return <= -abs(float(thresholds.get("abnormal_day", 1.0)))
    return BuildSignal(metrics.symbol, round(score, 2), tier, manual)
