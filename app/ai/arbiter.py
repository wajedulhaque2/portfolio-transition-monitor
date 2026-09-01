from __future__ import annotations

import logging

import httpx
from pydantic import ValidationError

from app.ai.base import AIProvider
from app.ai.schema import AIDecision

log = logging.getLogger(__name__)


def safe_decide(
    provider: AIProvider,
    payload: dict,
    max_amount: float,
    manual_required: bool = False,
) -> AIDecision:
    if manual_required:
        return AIDecision(
            decision="MANUAL_REVIEW",
            action_type="HOLD",
            amount_gbp=0,
            confidence=1,
            reason="Abnormal one-day move requires manual fundamental review",
            best_use_of_next_100="Keep cash pending manual review",
            manual_check_required=True,
        )

    try:
        result = provider.decide(
            {**payload, "max_amount_gbp": max_amount}
        )
    except (
        httpx.HTTPError,
        ValidationError,
        KeyError,
        IndexError,
        TypeError,
        ValueError,
    ) as exc:
        log.warning("AI decision unavailable: %s", type(exc).__name__)
        return AIDecision(
            decision="NO_ACTION",
            action_type="HOLD",
            amount_gbp=0,
            confidence=0,
            reason=f"AI unavailable ({type(exc).__name__}); failed closed",
            best_use_of_next_100="Keep cash and retry evaluation on a later scan",
            manual_check_required=False,
        )

    if result.amount_gbp > max_amount:
        result.amount_gbp = max_amount
        if result.decision == "APPROVE":
            result.decision = "DOWNSIZE"

    return result
