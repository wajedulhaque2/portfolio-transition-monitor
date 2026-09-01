from __future__ import annotations

from app.ai.schema import AIDecision

SYSTEM_PROMPT = (
    "Conservative portfolio arbiter. Return ONE JSON object only with "
    "exactly these keys: decision "
    "(APPROVE|DOWNSIZE|NO_ACTION|MANUAL_REVIEW), action_type "
    "(BUY|ADD|TRIM|ROTATE|HOLD), buy_ticker (string|null), "
    "sell_ticker (string|null), amount_gbp (number >=0), "
    "confidence (0..1), reason (string), "
    "best_use_of_next_100 (string), manual_check_required (boolean). "
    "Never exceed max_amount_gbp. "
    "Prefer NO_ACTION when evidence is marginal."
)

REPAIR_INSTRUCTION = (
    "Your previous response was invalid. Re-answer the same request. "
    "Return exactly one valid JSON object matching the required schema. "
    "Do not return markdown, code fences, commentary, or additional text."
)


def parse_decision_content(
    content: object,
) -> AIDecision:
    if (
        not isinstance(content, str)
        or not content.strip()
    ):
        raise ValueError(
            "AI returned empty or non-text content"
        )

    cleaned = content.strip()

    if cleaned.startswith("```"):
        lines = cleaned.splitlines()

        if (
            len(lines) >= 2
            and lines[-1].strip() == "```"
        ):
            lines = lines[1:-1]
            cleaned = "\n".join(
                lines
            ).strip()

    return AIDecision.model_validate_json(
        cleaned
    )