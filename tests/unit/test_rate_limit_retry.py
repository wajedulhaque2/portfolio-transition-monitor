from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

import httpx
import pytest

import app.utils_retry as retry_module
from app.market_data.twelve_data import (
    TwelveDataProvider,
)
from app.utils_retry import retry_call


def test_retry_call_is_bounded_and_exponential(
    monkeypatch,
):
    calls = 0
    delays: list[float] = []

    def fake_sleep(
        delay: float,
    ) -> None:
        delays.append(delay)

    monkeypatch.setattr(
        retry_module.time,
        "sleep",
        fake_sleep,
    )

    def always_fail() -> None:
        nonlocal calls
        calls += 1

        raise RuntimeError(
            "provider unavailable"
        )

    with pytest.raises(
        RuntimeError,
        match="provider unavailable",
    ):
        retry_call(
            always_fail
        )

    assert calls == 3
    assert delays == [
        0.5,
        1.0,
    ]


def _provider_with_transport(
    handler: Callable[
        [httpx.Request],
        httpx.Response,
    ],
) -> TwelveDataProvider:
    provider = TwelveDataProvider(
        "test-key"
    )

    provider.client.close()

    provider.client = httpx.Client(
        base_url="https://api.twelvedata.com",
        transport=httpx.MockTransport(
            handler
        ),
    )

    return provider


def test_twelve_data_recovers_after_two_429s(
    monkeypatch,
):
    calls = 0
    delays: list[float] = []

    def fake_sleep(
        delay: float,
    ) -> None:
        delays.append(delay)

    monkeypatch.setattr(
        retry_module.time,
        "sleep",
        fake_sleep,
    )

    timestamp = int(
        datetime(
            2026,
            9,
            1,
            16,
            30,
            tzinfo=UTC,
        ).timestamp()
    )

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        nonlocal calls
        calls += 1

        if calls < 3:
            return httpx.Response(
                429,
                request=request,
                json={
                    "message":
                        "rate limit exceeded"
                },
            )

        return httpx.Response(
            200,
            request=request,
            json={
                "symbol": "NVDA",
                "close": "219.33",
                "currency": "USD",
                "timestamp": timestamp,
            },
        )

    provider = _provider_with_transport(
        handler
    )

    try:
        quote = provider.quote(
            "NVDA"
        )
    finally:
        provider.client.close()

    assert calls == 3
    assert delays == [
        0.5,
        1.0,
    ]

    assert quote.symbol == "NVDA"
    assert quote.price == 219.33
    assert quote.timestamp == datetime(
        2026,
        9,
        1,
        16,
        30,
        tzinfo=UTC,
    )


def test_twelve_data_stops_after_three_429s(
    monkeypatch,
):
    calls = 0
    delays: list[float] = []

    def fake_sleep(
        delay: float,
    ) -> None:
        delays.append(delay)

    monkeypatch.setattr(
        retry_module.time,
        "sleep",
        fake_sleep,
    )

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        nonlocal calls
        calls += 1

        return httpx.Response(
            429,
            request=request,
            json={
                "message":
                    "rate limit exceeded"
            },
        )

    provider = _provider_with_transport(
        handler
    )

    try:
        with pytest.raises(
            httpx.HTTPStatusError
        ):
            provider.quote(
                "NVDA"
            )
    finally:
        provider.client.close()

    assert calls == 3

    assert delays == [
        0.5,
        1.0,
    ]