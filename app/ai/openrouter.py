from __future__ import annotations

import json

import httpx

from app.ai.base import AIProvider
from app.ai.response import (
    REPAIR_INSTRUCTION,
    SYSTEM_PROMPT,
    parse_decision_content,
)
from app.ai.schema import AIDecision


class OpenRouterProvider(AIProvider):
    def __init__(
        self,
        api_key: str,
        model: str,
        timeout: float = 30.0,
    ):
        self.model = model

        self.client = httpx.Client(
            base_url="https://openrouter.ai/api/v1",
            timeout=timeout,
            headers={
                "Authorization": f"Bearer {api_key}"
            },
        )

    def _request(
        self,
        payload: dict,
        *,
        repair: bool,
    ) -> object:
        system = SYSTEM_PROMPT

        if repair:
            system = (
                f"{system}\n\n"
                f"{REPAIR_INSTRUCTION}"
            )

        response = self.client.post(
            "/chat/completions",
            json={
                "model": self.model,
                "temperature": 0,
                "messages": [
                    {
                        "role": "system",
                        "content": system,
                    },
                    {
                        "role": "user",
                        "content": json.dumps(
                            payload
                        ),
                    },
                ],
            },
        )

        response.raise_for_status()

        data = response.json()

        if not isinstance(
            data,
            dict,
        ):
            raise TypeError(
                "OpenRouter returned invalid response type"
            )

        choices = data.get(
            "choices"
        )

        if (
            not isinstance(choices, list)
            or not choices
        ):
            raise ValueError(
                "OpenRouter response missing choices"
            )

        choice = choices[0]

        if not isinstance(
            choice,
            dict,
        ):
            raise TypeError(
                "OpenRouter returned invalid choice"
            )

        finish_reason = choice.get(
            "finish_reason"
        )

        if (
            finish_reason is not None
            and finish_reason != "stop"
        ):
            raise ValueError(
                "OpenRouter response did not finish cleanly: "
                f"{finish_reason}"
            )

        message = choice.get(
            "message"
        )

        if not isinstance(
            message,
            dict,
        ):
            raise TypeError(
                "OpenRouter response missing message"
            )

        return message.get(
            "content"
        )

    def decide(
        self,
        payload: dict,
    ) -> AIDecision:
        for attempt in range(2):
            try:
                content = self._request(
                    payload,
                    repair=attempt == 1,
                )

                return parse_decision_content(
                    content
                )

            except (
                KeyError,
                IndexError,
                TypeError,
                ValueError,
            ):
                if attempt == 0:
                    continue

                raise

        raise RuntimeError(
            "unreachable AI retry state"
        )