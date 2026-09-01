from __future__ import annotations


def round_tranche(value: float) -> float:
    if value < 50:
        return round(max(0.0, value), 2)
    steps = [50, 75, 100, 125, 150, 200, 250, 300, 400, 500]
    valid = [x for x in steps if x <= value]
    return float(max(valid) if valid else 50)


def buy_size(total: float, target_gap_gbp: float, strong: bool, max_pct: float) -> float:
    pct = 0.0125 if strong else 0.0075
    gap_part = 0.35 if strong else 0.25
    raw = min(total * pct, target_gap_gbp * gap_part, total * max_pct)
    return round_tranche(raw)


def trim_size(total: float, excess_gbp: float, strong: bool, max_pct: float) -> float:
    pct = 0.0125 if strong else 0.0075
    excess_part = 0.40 if strong else 0.25
    raw = min(total * pct, excess_gbp * excess_part, total * max_pct)
    return round_tranche(raw)
