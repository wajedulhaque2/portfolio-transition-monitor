from __future__ import annotations

from abc import ABC, abstractmethod

from app.ai.schema import AIDecision


class AIProvider(ABC):
    @abstractmethod
    def decide(self, payload: dict) -> AIDecision: ...


class DisabledAIProvider(AIProvider):
    def decide(self, payload: dict) -> AIDecision:
        return AIDecision(
            decision="NO_ACTION",
            action_type="HOLD",
            amount_gbp=0,
            confidence=0,
            reason="AI disabled",
            best_use_of_next_100="No AI decision",
            manual_check_required=False,
        )


class FallbackAIProvider(AIProvider):
    def __init__(self, providers: list[AIProvider]):
        self.providers = providers

    def decide(self, payload: dict) -> AIDecision:
        last: Exception | None = None
        for p in self.providers:
            try:
                return p.decide(payload)
            except Exception as exc:  # noqa: BLE001 - provider fallback must isolate arbitrary provider failures
                last = exc
        if last:
            raise last
        raise RuntimeError("no AI providers")
