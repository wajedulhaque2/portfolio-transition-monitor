from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import select

from app.config import get_settings
from app.db.models import ProviderHealthRecord
from app.db.session import Database

log = logging.getLogger(__name__)


def _database_url(
    explicit_url: str | None,
) -> str | None:
    if explicit_url is not None:
        return explicit_url

    settings = get_settings()

    # Automatic telemetry is intended for deployed
    # production operation. Tests/local development
    # can opt in explicitly by supplying database_url.
    if settings.app_env.lower() != "production":
        return None

    return settings.database_url


def _record_provider_health(
    provider: str,
    operation: str,
    *,
    success: bool,
    error_type: str = "",
    database_url: str | None = None,
    event_time: datetime | None = None,
) -> None:
    url = _database_url(
        database_url
    )

    if url is None:
        return

    db: Database | None = None

    try:
        timestamp = (
            event_time.astimezone(UTC)
            if event_time is not None
            else datetime.now(UTC)
        )

        db = Database(
            url
        )

        db.init()

        with db.session() as session:
            row = session.scalar(
                select(
                    ProviderHealthRecord
                ).where(
                    ProviderHealthRecord.provider
                    == provider
                )
            )

            if row is None:
                row = ProviderHealthRecord(
                    provider=provider,
                    updated_at=timestamp,
                    last_success_at=None,
                    last_failure_at=None,
                    last_operation="",
                    consecutive_failures=0,
                    total_successes=0,
                    total_failures=0,
                    last_error="",
                )

                session.add(
                    row
                )

            row.updated_at = timestamp
            row.last_operation = operation

            if success:
                row.last_success_at = timestamp
                row.total_successes += 1
                row.consecutive_failures = 0
                row.last_error = ""

            else:
                row.last_failure_at = timestamp
                row.total_failures += 1
                row.consecutive_failures += 1
                row.last_error = error_type

            session.commit()

    except Exception as exc:  # noqa: BLE001
        # Health telemetry must never break
        # the underlying provider operation.
        log.warning(
            "provider health persistence failed: "
            "provider=%s error=%s",
            provider,
            type(exc).__name__,
        )

    finally:
        if db is not None:
            db.close()


def record_provider_success(
    provider: str,
    operation: str,
    *,
    database_url: str | None = None,
    event_time: datetime | None = None,
) -> None:
    _record_provider_health(
        provider,
        operation,
        success=True,
        database_url=database_url,
        event_time=event_time,
    )


def record_provider_failure(
    provider: str,
    operation: str,
    exc: Exception,
    *,
    database_url: str | None = None,
    event_time: datetime | None = None,
) -> None:
    _record_provider_health(
        provider,
        operation,
        success=False,
        error_type=type(exc).__name__,
        database_url=database_url,
        event_time=event_time,
    )