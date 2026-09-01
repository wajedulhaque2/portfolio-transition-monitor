import json
from typing import Any

from app.ai.arbiter import safe_decide
from app.ai.nvidia import NvidiaProvider
from app.ai.openrouter import OpenRouterProvider


def valid_decision() -> str:
    return json.dumps(
        {
            "decision": "APPROVE",
            "action_type": "BUY",
            "buy_ticker": "GOOGL",
            "sell_ticker": None,
            "amount_gbp": 100,
            "confidence": 0.9,
            "reason": "Valid test response",
            "best_use_of_next_100": "GOOGL",
            "manual_check_required": False,
        }
    )


def response(
    content: object,
    *,
    finish_reason: str = "stop",
) -> dict[str, Any]:
    return {
        "choices": [
            {
                "finish_reason": finish_reason,
                "message": {
                    "content": content
                },
            }
        ]
    }


class FakeResponse:
    def __init__(
        self,
        payload: object,
    ):
        self.payload = payload

    def raise_for_status(
        self,
    ) -> None:
        return None

    def json(
        self,
    ) -> object:
        return self.payload


class FakeClient:
    def __init__(
        self,
        responses: list[object],
    ):
        self.responses = responses
        self.calls: list[
            dict[str, Any]
        ] = []

    def post(
        self,
        path: str,
        *,
        json: dict[str, Any],
    ) -> FakeResponse:
        del path

        self.calls.append(
            json
        )

        index = len(
            self.calls
        ) - 1

        return FakeResponse(
            self.responses[index]
        )


def make_nvidia(
    responses: list[object],
) -> tuple[NvidiaProvider, FakeClient]:
    provider = NvidiaProvider(
        "test-key",
        "test-model",
    )

    provider.client.close()

    client = FakeClient(
        responses
    )

    provider.client = client  # type: ignore[assignment]

    return provider, client


def make_openrouter(
    responses: list[object],
) -> tuple[OpenRouterProvider, FakeClient]:
    provider = OpenRouterProvider(
        "test-key",
        "test-model",
    )

    provider.client.close()

    client = FakeClient(
        responses
    )

    provider.client = client  # type: ignore[assignment]

    return provider, client


def repair_prompt(
    client: FakeClient,
) -> str:
    messages = client.calls[1][
        "messages"
    ]

    return str(
        messages[0]["content"]
    )


def test_nvidia_repairs_once_after_malformed_output():
    provider, client = make_nvidia(
        [
            response(
                "not-json"
            ),
            response(
                valid_decision()
            ),
        ]
    )

    result = provider.decide(
        {"candidate": {}}
    )

    assert result.decision == "APPROVE"
    assert len(client.calls) == 2

    assert (
        "previous response was invalid"
        in repair_prompt(
            client
        )
    )


def test_nvidia_valid_output_does_not_retry():
    provider, client = make_nvidia(
        [
            response(
                valid_decision()
            )
        ]
    )

    result = provider.decide(
        {"candidate": {}}
    )

    assert result.decision == "APPROVE"
    assert len(client.calls) == 1


def test_nvidia_second_malformed_output_fails_closed():
    provider, client = make_nvidia(
        [
            response(
                "bad-response-one"
            ),
            response(
                "bad-response-two"
            ),
        ]
    )

    result = safe_decide(
        provider,
        {},
        100,
    )

    assert len(client.calls) == 2
    assert result.decision == "NO_ACTION"
    assert result.amount_gbp == 0


def test_openrouter_repairs_once_after_malformed_output():
    provider, client = make_openrouter(
        [
            response(
                "not-json"
            ),
            response(
                valid_decision()
            ),
        ]
    )

    result = provider.decide(
        {"candidate": {}}
    )

    assert result.decision == "APPROVE"
    assert len(client.calls) == 2

    assert (
        "previous response was invalid"
        in repair_prompt(
            client
        )
    )


def test_openrouter_second_malformed_output_fails_closed():
    provider, client = make_openrouter(
        [
            response(
                "bad-response-one"
            ),
            response(
                "bad-response-two"
            ),
        ]
    )

    result = safe_decide(
        provider,
        {},
        100,
    )

    assert len(client.calls) == 2
    assert result.decision == "NO_ACTION"
    assert result.amount_gbp == 0
