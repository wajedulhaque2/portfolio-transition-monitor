from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import exchange_calendars as xcals

EXCHANGE_CALENDARS = {
    "NYSE": "XNYS",
    "NASDAQ": "XNAS",
    "LSE": "XLON",
}

OPEN_MARKET_MAX_AGE = timedelta(hours=2)
CLOSED_SESSION_GRACE = timedelta(hours=2)
FUTURE_TOLERANCE = timedelta(minutes=5)
HISTORY_SESSION_SETTLE_DELAY = timedelta(minutes=15)


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)

    return value.astimezone(UTC)


def latest_completed_session_date(
    exchange: str,
    *,
    now: datetime | None = None,
) -> date | None:
    calendar_name = EXCHANGE_CALENDARS.get(
        exchange.upper()
    )

    if calendar_name is None:
        return None

    current_time = _utc(
        now or datetime.now(UTC)
    )

    calendar = xcals.get_calendar(
        calendar_name
    )

    start = (
        current_time - timedelta(days=21)
    ).date()

    end = (
        current_time + timedelta(days=1)
    ).date()

    sessions = calendar.sessions_in_range(
        start.isoformat(),
        end.isoformat(),
    )

    latest: date | None = None

    for session in sessions:
        session_close = _utc(
            calendar.session_close(
                session
            ).to_pydatetime()
        )

        completed_at = (
            session_close
            + HISTORY_SESSION_SETTLE_DELAY
        )

        if completed_at <= current_time:
            latest = session.date()

    return latest


def is_quote_fresh(
    exchange: str,
    quote_timestamp: datetime,
    *,
    now: datetime | None = None,
) -> bool:
    calendar_name = EXCHANGE_CALENDARS.get(
        exchange.upper()
    )

    if calendar_name is None:
        return False

    current_time = _utc(
        now or datetime.now(UTC)
    )

    quote_time = _utc(
        quote_timestamp
    )

    if (
        quote_time
        > current_time + FUTURE_TOLERANCE
    ):
        return False

    calendar = xcals.get_calendar(
        calendar_name
    )

    start = (
        current_time - timedelta(days=21)
    ).date()

    end = (
        current_time + timedelta(days=1)
    ).date()

    sessions = calendar.sessions_in_range(
        start.isoformat(),
        end.isoformat(),
    )

    if len(sessions) == 0:
        return False

    latest_completed_open: datetime | None = None
    latest_completed_close: datetime | None = None

    for session in sessions:
        session_open = _utc(
            calendar.session_open(
                session
            ).to_pydatetime()
        )

        session_close = _utc(
            calendar.session_close(
                session
            ).to_pydatetime()
        )

        if (
            session_open
            <= current_time
            <= session_close
        ):
            age = (
                current_time - quote_time
            )

            return (
                quote_time
                >= session_open
                - FUTURE_TOLERANCE
                and age
                <= OPEN_MARKET_MAX_AGE
            )

        if session_close < current_time:
            latest_completed_open = (
                session_open
            )
            latest_completed_close = (
                session_close
            )

    if (
        latest_completed_open is None
        or latest_completed_close is None
    ):
        return False

    return (
        quote_time
        >= latest_completed_close
        - CLOSED_SESSION_GRACE
        and quote_time <= current_time
    )