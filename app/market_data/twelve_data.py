from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

import httpx

from app.market_data.base import (
    DailyBar,
    MarketDataProvider,
    Quote,
)
from app.market_data.provider_health import (
    record_provider_failure,
    record_provider_success,
)
from app.utils_retry import retry_call


def _parse_unix_timestamp(
    value: object,
) -> datetime | None:
    if (
        value is None
        or isinstance(
            value,
            bool,
        )
    ):
        return None

    if not isinstance(
        value,
        (
            str,
            int,
            float,
        ),
    ):
        return None

    if isinstance(
        value,
        str,
    ):
        value = value.strip()

        if not value:
            return None

    try:
        timestamp = float(
            value
        )

    except ValueError:
        return None

    if timestamp <= 0:
        return None

    try:
        return datetime.fromtimestamp(
            timestamp,
            tz=UTC,
        )

    except (
        OverflowError,
        OSError,
        ValueError,
    ):
        return None


def _quote_timestamp(
    payload: dict[
        str,
        Any,
    ],
) -> datetime:
    for key in (
        "last_quote_at",
        "timestamp",
    ):
        parsed = (
            _parse_unix_timestamp(
                payload.get(
                    key
                )
            )
        )

        if parsed is not None:
            return parsed

    raise RuntimeError(
        "Twelve Data quote missing "
        "valid market timestamp"
    )


class TwelveDataProvider(
    MarketDataProvider
):
    def __init__(
        self,
        api_key: str,
        timeout: float = 15.0,
    ):
        self.api_key = api_key

        self.client = httpx.Client(
            base_url=(
                "https://api.twelvedata.com"
            ),
            timeout=timeout,
        )

    def quote(
        self,
        symbol: str,
    ) -> Quote:
        try:
            def call() -> dict[
                str,
                Any,
            ]:
                response = (
                    self.client.get(
                        "/quote",
                        params={
                            "symbol": symbol,
                            "apikey": (
                                self.api_key
                            ),
                        },
                    )
                )

                response.raise_for_status()

                payload = (
                    response.json()
                )

                if not isinstance(
                    payload,
                    dict,
                ):
                    raise TypeError(
                        "invalid Twelve Data "
                        "quote response"
                    )

                return payload

            data = retry_call(
                call
            )

            if (
                "code" in data
                and int(
                    data.get(
                        "code",
                        0,
                    )
                )
                >= 400
            ):
                raise RuntimeError(
                    str(
                        data.get(
                            "message",
                            "Twelve Data error",
                        )
                    )
                )

            price = float(
                data.get(
                    "close"
                )
                or data.get(
                    "price"
                )
                or 0
            )

            if price <= 0:
                raise RuntimeError(
                    "invalid Twelve Data price"
                )

            timestamp = (
                _quote_timestamp(
                    data
                )
            )

            quote = Quote(
                symbol=symbol,
                price=price,
                timestamp=timestamp,
                currency=str(
                    data.get(
                        "currency"
                    )
                    or "USD"
                ),
            )

        except Exception as exc:
            record_provider_failure(
                "twelve_data",
                "quote",
                exc,
            )

            raise

        record_provider_success(
            "twelve_data",
            "quote",
        )

        return quote

    def history(
        self,
        symbol: str,
        outputsize: int = 260,
    ) -> list[DailyBar]:
        try:
            def call() -> dict[
                str,
                Any,
            ]:
                response = (
                    self.client.get(
                        "/time_series",
                        params={
                            "symbol": symbol,
                            "interval": "1day",
                            "outputsize": (
                                outputsize
                            ),
                            "order": "ASC",
                            "apikey": (
                                self.api_key
                            ),
                        },
                    )
                )

                response.raise_for_status()

                payload = (
                    response.json()
                )

                if not isinstance(
                    payload,
                    dict,
                ):
                    raise TypeError(
                        "invalid Twelve Data "
                        "history response"
                    )

                return payload

            data = retry_call(
                call
            )

            if (
                "code" in data
                and int(
                    data.get(
                        "code",
                        0,
                    )
                )
                >= 400
            ):
                raise RuntimeError(
                    str(
                        data.get(
                            "message",
                            "Twelve Data error",
                        )
                    )
                )

            values = (
                data.get(
                    "values"
                )
                or []
            )

            bars = [
                DailyBar(
                    date=date.fromisoformat(
                        str(
                            item[
                                "datetime"
                            ]
                        )[:10]
                    ),
                    open=float(
                        item[
                            "open"
                        ]
                    ),
                    high=float(
                        item[
                            "high"
                        ]
                    ),
                    low=float(
                        item[
                            "low"
                        ]
                    ),
                    close=float(
                        item[
                            "close"
                        ]
                    ),
                )
                for item in values
            ]

            if len(
                bars
            ) < 21:
                raise RuntimeError(
                    "insufficient Twelve Data "
                    "history"
                )

        except Exception as exc:
            record_provider_failure(
                "twelve_data",
                "history",
                exc,
            )

            raise

        record_provider_success(
            "twelve_data",
            "history",
        )

        return bars

    def close(
        self,
    ) -> None:
        self.client.close()