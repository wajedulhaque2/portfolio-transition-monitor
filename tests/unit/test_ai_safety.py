from app.ai.arbiter import safe_decide
from app.ai.base import AIProvider
from app.ai.schema import AIDecision


class BadAI(AIProvider):
    def decide(self, payload):
        return AIDecision(
            decision="APPROVE",
            action_type="BUY",
            buy_ticker="GOOGL",
            amount_gbp=500,
            confidence=0.9,
            reason="x",
            best_use_of_next_100="GOOGL",
        )


def test_ai_cannot_increase():
    decision = safe_decide(BadAI(), {}, 100)
    assert decision.amount_gbp == 100
    assert decision.decision == "DOWNSIZE"


def test_manual_override():
    decision = safe_decide(BadAI(), {}, 100, True)
    assert decision.decision == "MANUAL_REVIEW"
    assert decision.amount_gbp == 0
