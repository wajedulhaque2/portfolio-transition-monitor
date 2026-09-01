from datetime import UTC, date, datetime, timedelta

from app.db.session import Database
from app.market_data.base import DailyBar
from app.market_data.history_cache import HistoryCache


def make_bars(
    count: int = 30,
    *,
    start: date = date(2026, 1, 1),
) -> list[DailyBar]:
    bars: list[DailyBar] = []

    for i in range(count):
        value = 100.0 + i

        bars.append(
            DailyBar(
                date=start + timedelta(days=i),
                open=value - 1,
                high=value + 1,
                low=value - 2,
                close=value,
            )
        )

    return bars


def test_cache_miss_returns_none(tmp_path):
    db = Database(
        f"sqlite:///{tmp_path / 'cache.db'}"
    )
    db.init()

    try:
        cache = HistoryCache(db)

        assert (
            cache.get(
                "yahoo",
                "NVDA",
                date(2026, 1, 20),
            )
            is None
        )
    finally:
        db.close()


def test_cache_round_trip(tmp_path):
    db = Database(
        f"sqlite:///{tmp_path / 'cache.db'}"
    )
    db.init()

    try:
        cache = HistoryCache(db)
        bars = make_bars()

        stored = cache.put(
            "yahoo",
            "NVDA",
            bars,
            completed_through=bars[-1].date,
            now=datetime(
                2026,
                2,
                1,
                20,
                0,
                tzinfo=UTC,
            ),
        )

        loaded = cache.get(
            "yahoo",
            "NVDA",
            bars[-1].date,
        )

        assert loaded is not None
        assert len(loaded) == 30
        assert loaded[-1].date == bars[-1].date
        assert loaded[-1].close == bars[-1].close
        assert stored == loaded
    finally:
        db.close()


def test_cache_rejects_missing_completed_session(
    tmp_path,
):
    db = Database(
        f"sqlite:///{tmp_path / 'cache.db'}"
    )
    db.init()

    try:
        cache = HistoryCache(db)
        bars = make_bars()

        cache.put(
            "yahoo",
            "NVDA",
            bars,
            completed_through=bars[-1].date,
        )

        assert (
            cache.get(
                "yahoo",
                "NVDA",
                bars[-1].date
                + timedelta(days=1),
            )
            is None
        )
    finally:
        db.close()


def test_cache_removes_incomplete_current_bar(
    tmp_path,
):
    db = Database(
        f"sqlite:///{tmp_path / 'cache.db'}"
    )
    db.init()

    try:
        cache = HistoryCache(db)
        bars = make_bars(31)

        completed_through = bars[-2].date

        stored = cache.put(
            "yahoo",
            "NVDA",
            bars,
            completed_through=completed_through,
        )

        assert stored[-1].date == completed_through
        assert len(stored) == 30

        loaded = cache.get(
            "yahoo",
            "NVDA",
            completed_through,
        )

        assert loaded is not None
        assert loaded[-1].date == completed_through
    finally:
        db.close()


def test_cache_upsert_replaces_old_history(
    tmp_path,
):
    db = Database(
        f"sqlite:///{tmp_path / 'cache.db'}"
    )
    db.init()

    try:
        cache = HistoryCache(db)

        first = make_bars(30)
        second = make_bars(31)

        cache.put(
            "yahoo",
            "NVDA",
            first,
            completed_through=first[-1].date,
        )

        cache.put(
            "yahoo",
            "NVDA",
            second,
            completed_through=second[-1].date,
        )

        loaded = cache.get(
            "yahoo",
            "NVDA",
            second[-1].date,
        )

        assert loaded is not None
        assert len(loaded) == 31
        assert loaded[-1].date == second[-1].date
    finally:
        db.close()