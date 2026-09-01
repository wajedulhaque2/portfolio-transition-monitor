from __future__ import annotations

from typing import Any

import httpx

from app.market_data.provider_health import (
    record_provider_failure,
    record_provider_success,
)
from app.utils_retry import retry_call

ALLOWED_GET_PATHS = {
    "/equity/account/summary",
    "/equity/positions",
    "/equity/orders",
    "/equity/metadata/instruments",
    "/equity/metadata/exchanges",
}


class Trading212Client:
    """Read-only client. Deliberately exposes GET methods only."""

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        environment: str = "demo",
        timeout: float = 15.0,
    ):
        base = (
            "https://demo.trading212.com/api/v0"
            if environment == "demo"
            else "https://live.trading212.com/api/v0"
        )

        self.client = httpx.Client(
            base_url=base,
            auth=(
                api_key,
                api_secret,
            ),
            timeout=timeout,
        )

    def _get(
        self,
        path: str,
    ) -> Any:
        if path not in ALLOWED_GET_PATHS:
            raise ValueError(
                "Trading 212 path not "
                f"allowlisted: {path}"
            )

        operation = (
            path.removeprefix(
                "/equity/"
            )
            .replace(
                "/",
                "_",
            )
        )

        try:
            def call() -> Any:
                response = (
                    self.client.get(
                        path
                    )
                )

                response.raise_for_status()

                return response.json()

            result = retry_call(
                call
            )

        except Exception as exc:
            record_provider_failure(
                "trading212",
                operation,
                exc,
            )

            raise

        record_provider_success(
            "trading212",
            operation,
        )

        return result

    def account_summary(
        self,
    ) -> Any:
        return self._get(
            "/equity/account/summary"
        )

    def positions(
        self,
    ) -> Any:
        return self._get(
            "/equity/positions"
        )

    def orders(
        self,
    ) -> Any:
        return self._get(
            "/equity/orders"
        )

    def instruments(
        self,
    ) -> Any:
        return self._get(
            "/equity/metadata/instruments"
        )

    def exchanges(
        self,
    ) -> Any:
        return self._get(
            "/equity/metadata/exchanges"
        )

    def close(
        self,
    ) -> None:
        self.client.close()