from datetime import UTC, date, datetime

from app.market_data.freshness import (
    is_quote_fresh,
    latest_completed_session_date,
)


def utc(
    year: int,
    month: int,
    day: int,
    hour: int,
    minute: int = 0,
) -> datetime:
    return datetime(
        year,
        month,
        day,
        hour,
        minute,
        tzinfo=UTC,
    )


def test_us_previous_close_is_fresh_before_market_opens():
    assert is_quote_fresh(
        "NYSE",
        utc(2026, 8, 31, 20, 0),
        now=utc(2026, 9, 1, 12, 0),
    )


def test_us_previous_close_is_stale_during_open_market():
    assert not is_quote_fresh(
        "NYSE",
        utc(2026, 8, 31, 20, 0),
        now=utc(2026, 9, 1, 15, 0),
    )


def test_us_recent_quote_is_fresh_during_open_market():
    assert is_quote_fresh(
        "NASDAQ",
        utc(2026, 9, 1, 14, 45),
        now=utc(2026, 9, 1, 15, 0),
    )


def test_lse_previous_close_is_valid_on_bank_holiday():
    assert is_quote_fresh(
        "LSE",
        utc(2026, 8, 28, 15, 30),
        now=utc(2026, 8, 31, 12, 0),
    )


def test_lse_old_quote_is_stale_once_next_session_is_open():
    assert not is_quote_fresh(
        "LSE",
        utc(2026, 8, 28, 15, 30),
        now=utc(2026, 9, 1, 10, 0),
    )


def test_unknown_exchange_fails_closed():
    assert not is_quote_fresh(
        "UNKNOWN",
        utc(2026, 9, 1, 10, 0),
        now=utc(2026, 9, 1, 10, 5),
    )


def test_future_quote_fails_closed():
    assert not is_quote_fresh(
        "NYSE",
        utc(2026, 9, 1, 16, 0),
        now=utc(2026, 9, 1, 15, 0),
    )


def test_latest_completed_us_session_during_market():
    result = latest_completed_session_date(
        "NYSE",
        now=utc(2026, 9, 1, 15, 0),
    )

    assert result == date(
        2026,
        8,
        31,
    )


def test_completed_session_waits_for_settle_delay():
    result = latest_completed_session_date(
        "NYSE",
        now=utc(2026, 9, 1, 20, 5),
    )

    assert result == date(
        2026,
        8,
        31,
    )


def test_session_becomes_completed_after_settle_delay():
    result = latest_completed_session_date(
        "NYSE",
        now=utc(2026, 9, 1, 20, 20),
    )

    assert result == date(
        2026,
        9,
        1,
    )


def test_latest_lse_session_across_bank_holiday():
    result = latest_completed_session_date(
        "LSE",
        now=utc(2026, 8, 31, 12, 0),
    )

    assert result == date(
        2026,
        8,
        28,
    )


def test_latest_session_unknown_exchange_returns_none():
    assert (
        latest_completed_session_date(
            "UNKNOWN",
            now=utc(
                2026,
                9,
                1,
                15,
                0,
            ),
        )
        is None
    )