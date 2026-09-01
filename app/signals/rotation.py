from __future__ import annotations

from dataclasses import dataclass

from app.signals.build import BuildSignal
from app.signals.trim import TrimSignal


@dataclass(slots=True)
class RotationSignal:
    sell_symbol: str
    buy_symbol: str
    score: float
    tier: str


def rotation_score(
    trim: TrimSignal, build: BuildSignal, diversification_bonus: float = 0.15
) -> RotationSignal:
    score = (
        0.45 * build.score + 0.40 * trim.score + 100 * max(0.0, min(0.15, diversification_bonus))
    )
    if score >= 85:
        tier = "STRONG"
    elif score >= 75:
        tier = "REVIEW"
    elif score >= 65:
        tier = "WATCH"
    else:
        tier = "IGNORE"
    return RotationSignal(trim.symbol, build.symbol, round(score, 2), tier)
