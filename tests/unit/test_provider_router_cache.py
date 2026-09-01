from datetime import UTC, date, datetime, timedelta

from app.db.session import Database
from app.jobs.live import ProviderRouter
from app.market_data.base import DailyBar, MarketDataProvider, Quote
from app.market_data.history_cache import HistoryCache


class CountingProvider(
    MarketDataProvider
):
    def __init__(
        self,
        bars: list[DailyBar],
    ):
        self.bars = bars
        self.quote_calls = 0
        self.history_calls = 0

    def quote(
        self,
        symbol: str,
    ) -> Quote:
        self.quote_calls += 1

        return Quote(
            symbol=symbol,
            price=200.0,
            timestamp=datetime(
                2026,
                9,
                1,
                15,
                0,
                tzinfo=UTC,
            ),
            currency="USD",
        )

    def history(
        self,
        symbol: str,
        outputsize: int = 260,
    ) -> list[DailyBar]:
        del symbol
        del outputsize

        self.history_calls += 1

        return list(
            self.bars
        )


def make_bars() -> list[DailyBar]:
    start = date(
        2026,
        8,
        1,
    )

    bars: list[DailyBar] = []

    for i in range(32):
        value = 100.0 + i

        bars.append(
            DailyBar(
                date=start
                + timedelta(days=i),
                open=value - 1,
                high=value + 1,
                low=value - 2,
                close=value,
            )
        )

    return bars


def meta() -> dict:
    return {
        "yahoo": "NVDA",
        "twelve_data": None,
        "exchange": "NYSE",
    }


def test_hourly_fetch_reuses_cached_history(
    tmp_path,
):
    db = Database(
        f"sqlite:///{tmp_path / 'router.db'}"
    )
    db.init()

    try:
        provider = CountingProvider(
            make_bars()
        )

        router = ProviderRouter(
            None,
            yahoo=provider,
            history_cache=HistoryCache(
                db
            ),
        )

        now = datetime(
            2026,
            9,
            1,
            15,
            0,
            tzinfo=UTC,
        )

        first = router.fetch(
            meta(),
            now=now,
        )

        second = router.fetch(
            meta(),
            now=now,
        )

        assert provider.quote_calls == 2
        assert provider.history_calls == 1

        assert (
            first[2][-1].date
            == date(
                2026,
                8,
                31,
            )
        )

        assert (
            second[2][-1].date
            == date(
                2026,
                8,
                31,
            )
        )

    finally:
        db.close()


def test_new_completed_session_refreshes_history(
    tmp_path,
):
    db = Database(
        f"sqlite:///{tmp_path / 'router.db'}"
    )
    db.init()

    try:
        provider = CountingProvider(
            make_bars()
        )

        router = ProviderRouter(
            None,
            yahoo=provider,
            history_cache=HistoryCache(
                db
            ),
        )

        router.fetch(
            meta(),
            now=datetime(
                2026,
                9,
                1,
                15,
                0,
                tzinfo=UTC,
            ),
        )

        result = router.fetch(
            meta(),
            now=datetime(
                2026,
                9,
                1,
                20,
                20,
                tzinfo=UTC,
            ),
        )

        assert (
            provider.history_calls
            == 2
        )

        assert (
            result[2][-1].date
            == date(
                2026,
                9,
                1,
            )
        )

    finally:
        db.close()


def test_cache_survives_router_recreation(
    tmp_path,
):
    db = Database(
        f"sqlite:///{tmp_path / 'router.db'}"
    )
    db.init()

    try:
        cache = HistoryCache(
            db
        )

        first_provider = CountingProvider(
            make_bars()
        )

        first_router = ProviderRouter(
            None,
            yahoo=first_provider,
            history_cache=cache,
        )

        now = datetime(
            2026,
            9,
            1,
            15,
            0,
            tzinfo=UTC,
        )

        first_router.fetch(
            meta(),
            now=now,
        )

        assert (
            first_provider.history_calls
            == 1
        )

        second_provider = CountingProvider(
            make_bars()
        )

        second_router = ProviderRouter(
            None,
            yahoo=second_provider,
            history_cache=HistoryCache(
                db
            ),
        )

        result = second_router.fetch(
            meta(),
            now=now,
        )

        assert (
            second_provider.quote_calls
            == 1
        )

        assert (
            second_provider.history_calls
            == 0
        )

        assert (
            result[2][-1].date
            == date(
                2026,
                8,
                31,
            )
        )

    finally:
        db.close()
