from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select

import app.market_data.provider_health as health_module
import app.utils_retry as retry_module
from app.db.models import ProviderHealthRecord
from app.db.session import Database
from app.jobs.live import ProviderRouter
from app.market_data.twelve_data import TwelveDataProvider
from app.market_data.yahoo import YahooProvider


class FailingYahooClient:
    def get(
        self,
        path: str,
        params: dict | None = None,
    ):
        del path
        del params

        raise RuntimeError(
            "simulated Yahoo outage"
        )

    def close(
        self,
    ) -> None:
        pass


class FakeResponse:
    def __init__(
        self,
        payload: dict,
    ):
        self.payload = payload

    def raise_for_status(
        self,
    ) -> None:
        pass

    def json(
        self,
    ) -> dict:
        return self.payload


class SuccessfulTwelveClient:
    def __init__(
        self,
    ):
        self.quote_calls = 0
        self.history_calls = 0

    def get(
        self,
        path: str,
        params: dict | None = None,
    ) -> FakeResponse:
        del params

        if path == "/quote":
            self.quote_calls += 1

            timestamp = int(
                datetime(
                    2026,
                    9,
                    1,
                    15,
                    0,
                    tzinfo=UTC,
                ).timestamp()
            )

            return FakeResponse(
                {
                    "symbol": "NVDA",
                    "close": "180.25",
                    "currency": "USD",
                    "timestamp": timestamp,
                }
            )

        if path == "/time_series":
            self.history_calls += 1

            start = date(
                2026,
                8,
                1,
            )

            values = []

            for index in range(32):
                day = (
                    start
                    + timedelta(
                        days=index
                    )
                )

                price = (
                    150.0
                    + index
                )

                values.append(
                    {
                        "datetime": (
                            day.isoformat()
                        ),
                        "open": str(
                            price - 1
                        ),
                        "high": str(
                            price + 1
                        ),
                        "low": str(
                            price - 2
                        ),
                        "close": str(
                            price
                        ),
                    }
                )

            return FakeResponse(
                {
                    "values": values,
                }
            )

        raise AssertionError(
            f"unexpected Twelve Data path: {path}"
        )

    def close(
        self,
    ) -> None:
        pass


def test_yahoo_failure_falls_back_to_twelve_and_records_health(
    tmp_path,
    monkeypatch,
):
    database_url = (
        f"sqlite:///{tmp_path}/"
        "provider_fallback.db"
    )

    monkeypatch.setattr(
        health_module,
        "_database_url",
        lambda explicit_url: (
            explicit_url
            or database_url
        ),
    )

    monkeypatch.setattr(
        retry_module.time,
        "sleep",
        lambda seconds: None,
    )

    yahoo = YahooProvider()
    twelve = TwelveDataProvider(
        "test-key"
    )

    yahoo.client.close()
    twelve.client.close()

    yahoo.client = (
        FailingYahooClient()
    )

    twelve_client = (
        SuccessfulTwelveClient()
    )

    twelve.client = (
        twelve_client
    )

    router = ProviderRouter(
        twelve=twelve,
        yahoo=yahoo,
        history_cache=None,
    )

    try:
        source, quote, bars = (
            router.fetch(
                {
                    "yahoo": "NVDA",
                    "twelve_data": "NVDA",
                    "exchange": "NASDAQ",
                },
                now=datetime(
                    2026,
                    9,
                    1,
                    15,
                    0,
                    tzinfo=UTC,
                ),
            )
        )

        assert source == "twelve_data"
        assert quote.symbol == "NVDA"
        assert quote.price == 180.25
        assert len(bars) == 32

        assert (
            twelve_client.quote_calls
            == 1
        )

        assert (
            twelve_client.history_calls
            == 1
        )

        db = Database(
            database_url
        )

        try:
            db.init()

            with db.session() as session:
                rows = {
                    row.provider: row
                    for row
                    in session.scalars(
                        select(
                            ProviderHealthRecord
                        )
                    )
                }

            assert set(
                rows
            ) == {
                "yahoo",
                "twelve_data",
            }

            yahoo_health = rows[
                "yahoo"
            ]

            assert (
                yahoo_health.total_failures
                == 1
            )

            assert (
                yahoo_health.total_successes
                == 0
            )

            assert (
                yahoo_health.consecutive_failures
                == 1
            )

            assert (
                yahoo_health.last_operation
                == "quote"
            )

            assert (
                yahoo_health.last_error
                == "RuntimeError"
            )

            twelve_health = rows[
                "twelve_data"
            ]

            assert (
                twelve_health.total_failures
                == 0
            )

            assert (
                twelve_health.total_successes
                == 2
            )

            assert (
                twelve_health.consecutive_failures
                == 0
            )

            assert (
                twelve_health.last_operation
                == "history"
            )

            assert (
                twelve_health.last_error
                == ""
            )

        finally:
            db.close()

    finally:
        yahoo.close()
        twelve.close()
