from datetime import UTC, datetime

import pytest

from app.market_data.freshness import is_quote_fresh
from app.market_data.twelve_data import TwelveDataProvider


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
        payload: object,
    ):
        self.payload = payload

    def get(
        self,
        *args,
        **kwargs,
    ) -> FakeResponse:
        del args
        del kwargs

        return FakeResponse(
            self.payload
        )


def provider_with_payload(
    payload: object,
) -> TwelveDataProvider:
    provider = TwelveDataProvider(
        "test-key"
    )

    provider.client.close()

    provider.client = FakeClient(  # type: ignore[assignment]
        payload
    )

    return provider


def test_quote_prefers_last_quote_at():
    provider = provider_with_payload(
        {
            "symbol": "NVDA",
            "close": "200.50",
            "currency": "USD",
            "timestamp": 1_700_000_000,
            "last_quote_at": 1_700_000_123,
        }
    )

    quote = provider.quote(
        "NVDA"
    )

    assert (
        int(
            quote.timestamp.timestamp()
        )
        == 1_700_000_123
    )


def test_quote_falls_back_to_timestamp():
    provider = provider_with_payload(
        {
            "symbol": "NVDA",
            "close": "200.50",
            "currency": "USD",
            "timestamp": 1_700_000_000,
        }
    )

    quote = provider.quote(
        "NVDA"
    )

    assert (
        int(
            quote.timestamp.timestamp()
        )
        == 1_700_000_000
    )


def test_invalid_last_quote_at_uses_timestamp():
    provider = provider_with_payload(
        {
            "symbol": "NVDA",
            "close": "200.50",
            "currency": "USD",
            "last_quote_at": "invalid",
            "timestamp": 1_700_000_000,
        }
    )

    quote = provider.quote(
        "NVDA"
    )

    assert (
        int(
            quote.timestamp.timestamp()
        )
        == 1_700_000_000
    )


def test_quote_without_provider_timestamp_fails_closed():
    provider = provider_with_payload(
        {
            "symbol": "NVDA",
            "close": "200.50",
            "currency": "USD",
        }
    )

    with pytest.raises(
        RuntimeError,
        match="market timestamp",
    ):
        provider.quote(
            "NVDA"
        )


def test_stale_twelve_data_quote_is_not_marked_fresh():
    old_market_time = datetime(
        2026,
        8,
        31,
        20,
        0,
        tzinfo=UTC,
    )

    provider = provider_with_payload(
        {
            "symbol": "NVDA",
            "close": "200.50",
            "currency": "USD",
            "last_quote_at": int(
                old_market_time.timestamp()
            ),
        }
    )

    quote = provider.quote(
        "NVDA"
    )

    assert not is_quote_fresh(
        "NASDAQ",
        quote.timestamp,
        now=datetime(
            2026,
            9,
            1,
            15,
            0,
            tzinfo=UTC,
        ),
    )