from __future__ import annotations

from datetime import UTC, datetime

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


class YahooProvider(MarketDataProvider):
    """Unofficial fallback using Yahoo's public chart endpoint."""

    def __init__(
        self,
        timeout: float = 15.0,
    ):
        self.client = httpx.Client(
            base_url="https://query1.finance.yahoo.com",
            timeout=timeout,
            headers={
                "User-Agent": "Mozilla/5.0",
            },
        )

    def _chart(
        self,
        symbol: str,
        range_: str = "1y",
    ) -> dict:
        def call() -> dict:
            response = self.client.get(
                f"/v8/finance/chart/{symbol}",
                params={
                    "interval": "1d",
                    "range": range_,
                },
            )

            response.raise_for_status()

            payload = response.json()

            if not isinstance(
                payload,
                dict,
            ):
                raise TypeError(
                    "invalid Yahoo response"
                )

            return payload

        data = retry_call(
            call
        )

        result = (
            (
                data.get("chart")
                or {}
            ).get("result")
            or [None]
        )[0]

        if not result:
            raise RuntimeError(
                "Yahoo no result"
            )

        if not isinstance(
            result,
            dict,
        ):
            raise TypeError(
                "invalid Yahoo chart result"
            )

        return result

    def quote(
        self,
        symbol: str,
    ) -> Quote:
        try:
            result = self._chart(
                symbol,
                "5d",
            )

            meta = (
                result.get("meta")
                or {}
            )

            price = float(
                meta.get(
                    "regularMarketPrice"
                )
                or 0
            )

            if price <= 0:
                raise RuntimeError(
                    "Yahoo invalid price"
                )

            market_time = meta.get(
                "regularMarketTime"
            )

            if market_time is None:
                raise RuntimeError(
                    "Yahoo missing market timestamp"
                )

            timestamp = datetime.fromtimestamp(
                int(
                    market_time
                ),
                tz=UTC,
            )

            quote = Quote(
                symbol=symbol,
                price=price,
                timestamp=timestamp,
                currency=str(
                    meta.get(
                        "currency"
                    )
                    or "USD"
                ),
            )

        except Exception as exc:
            record_provider_failure(
                "yahoo",
                "quote",
                exc,
            )
            raise

        record_provider_success(
            "yahoo",
            "quote",
        )

        return quote

    def history(
        self,
        symbol: str,
        outputsize: int = 260,
    ) -> list[DailyBar]:
        try:
            result = self._chart(
                symbol,
                "2y",
            )

            timestamps = (
                result.get(
                    "timestamp"
                )
                or []
            )

            quote = (
                (
                    (
                        result.get(
                            "indicators"
                        )
                        or {}
                    ).get(
                        "quote"
                    )
                    or [None]
                )[0]
                or {}
            )

            bars: list[DailyBar] = []

            for i, timestamp in enumerate(
                timestamps
            ):
                try:
                    values = [
                        quote[key][i]
                        for key in (
                            "open",
                            "high",
                            "low",
                            "close",
                        )
                    ]

                    if any(
                        value is None
                        for value in values
                    ):
                        continue

                    bar_date = (
                        datetime.fromtimestamp(
                            int(
                                timestamp
                            ),
                            tz=UTC,
                        ).date()
                    )

                    bars.append(
                        DailyBar(
                            bar_date,
                            *(
                                float(
                                    value
                                )
                                for value
                                in values
                            ),
                        )
                    )

                except (
                    IndexError,
                    KeyError,
                    TypeError,
                    ValueError,
                ):
                    continue

            if len(bars) < 21:
                raise RuntimeError(
                    "Yahoo insufficient history"
                )

            result_bars = bars[
                -outputsize:
            ]

        except Exception as exc:
            record_provider_failure(
                "yahoo",
                "history",
                exc,
            )
            raise

        record_provider_success(
            "yahoo",
            "history",
        )

        return result_bars

    def close(
        self,
    ) -> None:
        self.client.close()