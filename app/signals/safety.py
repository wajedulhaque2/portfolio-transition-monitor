from __future__ import annotations


def abnormal_drop(one_day_return: float, abnormal_threshold: float) -> bool:
    return one_day_return <= -abs(abnormal_threshold)


def cash_purchase_allowed(cash_gbp: float, amount_gbp: float, hard_min_cash_gbp: float) -> bool:
    return cash_gbp - amount_gbp >= hard_min_cash_gbp
