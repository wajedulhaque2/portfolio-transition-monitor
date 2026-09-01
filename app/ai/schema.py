from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class AIDecision(BaseModel):
    decision: Literal["APPROVE", "DOWNSIZE", "NO_ACTION", "MANUAL_REVIEW"]
    action_type: Literal["BUY", "ADD", "TRIM", "ROTATE", "HOLD"]
    buy_ticker: str | None = None
    sell_ticker: str | None = None
    amount_gbp: float = Field(ge=0)
    confidence: float = Field(ge=0, le=1)
    reason: str
    best_use_of_next_100: str
    manual_check_required: bool = False
