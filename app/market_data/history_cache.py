from __future__ import annotations

import json
from datetime import UTC, date, datetime

from sqlalchemy import select

from app.db.models import MarketHistoryCacheRecord
from app.db.session import Database
from app.market_data.base import DailyBar


class HistoryCache:
    def __init__(
        self,
        db: Database,
    ):
        self.db = db

    def get(
        self,
        source: str,
        symbol: str,
        required_through: date,
    ) -> list[DailyBar] | None:
        with self.db.session() as session:
            row = session.scalar(
                select(
                    MarketHistoryCacheRecord
                ).where(
                    MarketHistoryCacheRecord.source
                    == source,
                    MarketHistoryCacheRecord.symbol
                    == symbol,
                )
            )

            if row is None:
                return None

            try:
                latest = date.fromisoformat(
                    row.latest_bar_date
                )
            except ValueError:
                return None

            if latest < required_through:
                return None

            try:
                raw = json.loads(
                    row.payload
                )
            except (
                json.JSONDecodeError,
                TypeError,
            ):
                return None

        bars: list[DailyBar] = []

        try:
            for item in raw:
                bars.append(
                    DailyBar(
                        date=date.fromisoformat(
                            str(item["date"])
                        ),
                        open=float(
                            item["open"]
                        ),
                        high=float(
                            item["high"]
                        ),
                        low=float(
                            item["low"]
                        ),
                        close=float(
                            item["close"]
                        ),
                    )
                )
        except (
            KeyError,
            TypeError,
            ValueError,
        ):
            return None

        if len(bars) < 21:
            return None

        return bars

    def put(
        self,
        source: str,
        symbol: str,
        bars: list[DailyBar],
        *,
        completed_through: date,
        now: datetime | None = None,
    ) -> list[DailyBar]:
        completed = [
            bar
            for bar in bars
            if bar.date <= completed_through
        ]

        if len(completed) < 21:
            raise ValueError(
                "history cache requires at least "
                "21 completed daily bars"
            )

        completed = completed[-260:]

        payload = json.dumps(
            [
                {
                    "date": bar.date.isoformat(),
                    "open": bar.open,
                    "high": bar.high,
                    "low": bar.low,
                    "close": bar.close,
                }
                for bar in completed
            ],
            separators=(",", ":"),
        )

        updated_at = (
            now.astimezone(UTC)
            if now is not None
            else datetime.now(UTC)
        )

        latest_bar_date = (
            completed[-1].date.isoformat()
        )

        with self.db.session() as session:
            row = session.scalar(
                select(
                    MarketHistoryCacheRecord
                ).where(
                    MarketHistoryCacheRecord.source
                    == source,
                    MarketHistoryCacheRecord.symbol
                    == symbol,
                )
            )

            if row is None:
                row = MarketHistoryCacheRecord(
                    source=source,
                    symbol=symbol,
                    updated_at=updated_at,
                    latest_bar_date=latest_bar_date,
                    payload=payload,
                )
                session.add(
                    row
                )

            else:
                row.updated_at = updated_at
                row.latest_bar_date = (
                    latest_bar_date
                )
                row.payload = payload

            session.commit()

        return completed