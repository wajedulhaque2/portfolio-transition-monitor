from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select

import app.market_data.provider_health as health_module
from app.db.models import ProviderHealthRecord
from app.db.session import Database
from app.market_data.provider_health import (
    record_provider_failure,
    record_provider_success,
)


def test_provider_health_tracks_success_and_failure(
    tmp_path,
):
    database_url = (
        f"sqlite:///{tmp_path}/"
        "provider_health.db"
    )

    first = datetime(
        2026,
        9,
        1,
        12,
        0,
        tzinfo=UTC,
    )

    second = datetime(
        2026,
        9,
        1,
        12,
        1,
        tzinfo=UTC,
    )

    third = datetime(
        2026,
        9,
        1,
        12,
        2,
        tzinfo=UTC,
    )

    record_provider_success(
        "yahoo",
        "quote",
        database_url=database_url,
        event_time=first,
    )

    record_provider_failure(
        "yahoo",
        "history",
        RuntimeError(
            "sensitive provider detail"
        ),
        database_url=database_url,
        event_time=second,
    )

    record_provider_failure(
        "yahoo",
        "history",
        ValueError(
            "another sensitive detail"
        ),
        database_url=database_url,
        event_time=third,
    )

    db = Database(
        database_url
    )

    try:
        db.init()

        with db.session() as session:
            row = session.scalar(
                select(
                    ProviderHealthRecord
                ).where(
                    ProviderHealthRecord.provider
                    == "yahoo"
                )
            )

            assert row is not None

            assert (
                row.total_successes
                == 1
            )

            assert (
                row.total_failures
                == 2
            )

            assert (
                row.consecutive_failures
                == 2
            )

            assert (
                row.last_operation
                == "history"
            )

            assert (
                row.last_error
                == "ValueError"
            )

            assert (
                "sensitive"
                not in row.last_error
            )

            assert (
                row.last_success_at
                is not None
            )

            assert (
                row.last_failure_at
                is not None
            )

    finally:
        db.close()


def test_success_resets_consecutive_failures(
    tmp_path,
):
    database_url = (
        f"sqlite:///{tmp_path}/"
        "provider_health.db"
    )

    record_provider_failure(
        "twelve_data",
        "quote",
        RuntimeError(
            "temporary outage"
        ),
        database_url=database_url,
    )

    record_provider_failure(
        "twelve_data",
        "quote",
        RuntimeError(
            "temporary outage"
        ),
        database_url=database_url,
    )

    record_provider_success(
        "twelve_data",
        "quote",
        database_url=database_url,
    )

    db = Database(
        database_url
    )

    try:
        db.init()

        with db.session() as session:
            row = session.scalar(
                select(
                    ProviderHealthRecord
                ).where(
                    ProviderHealthRecord.provider
                    == "twelve_data"
                )
            )

            assert row is not None

            assert (
                row.total_successes
                == 1
            )

            assert (
                row.total_failures
                == 2
            )

            assert (
                row.consecutive_failures
                == 0
            )

            assert row.last_error == ""

    finally:
        db.close()


def test_multiple_providers_are_separate(
    tmp_path,
):
    database_url = (
        f"sqlite:///{tmp_path}/"
        "provider_health.db"
    )

    record_provider_success(
        "yahoo",
        "quote",
        database_url=database_url,
    )

    record_provider_success(
        "trading212",
        "account_summary",
        database_url=database_url,
    )

    db = Database(
        database_url
    )

    try:
        db.init()

        with db.session() as session:
            rows = list(
                session.scalars(
                    select(
                        ProviderHealthRecord
                    )
                )
            )

        assert {
            row.provider
            for row in rows
        } == {
            "yahoo",
            "trading212",
        }

    finally:
        db.close()


def test_health_persistence_failure_is_fail_safe(
    monkeypatch,
):
    class BrokenDatabase:
        def __init__(
            self,
            url: str,
        ):
            del url

            raise RuntimeError(
                "database unavailable"
            )

    monkeypatch.setattr(
        health_module,
        "Database",
        BrokenDatabase,
    )

    # Provider-health telemetry itself
    # must never break a scan.
    record_provider_success(
        "yahoo",
        "quote",
        database_url=(
            "sqlite:///unused.db"
        ),
    )