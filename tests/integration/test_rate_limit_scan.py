from __future__ import annotations

from datetime import datetime

import httpx
from sqlalchemy import select

from app.ai.base import DisabledAIProvider
from app.db.models import (
    AlertRecord,
    ScanRun,
)
from app.db.session import Database
from app.jobs.live import LiveRunner
from app.notifications.base import Notifier
from app.portfolio.models import PortfolioState


class DummyT212:
    pass


class RateLimitedRouter:
    def __init__(self):
        self.calls = 0

    def fetch(
        self,
        meta: dict,
        *,
        now: datetime | None = None,
    ):
        del meta, now

        self.calls += 1

        request = httpx.Request(
            "GET",
            "https://provider.test/quote",
        )

        response = httpx.Response(
            429,
            request=request,
            json={
                "message":
                    "rate limit exceeded"
            },
        )

        raise httpx.HTTPStatusError(
            "429 Too Many Requests",
            request=request,
            response=response,
        )


class RecordingNotifier(Notifier):
    def __init__(self):
        self.messages: list[str] = []

    def send(
        self,
        message: str,
    ) -> None:
        self.messages.append(
            message
        )


def test_full_scan_fails_closed_when_market_data_is_rate_limited(
    tmp_path,
    monkeypatch,
):
    db = Database(
        f"sqlite:///{tmp_path}/"
        "rate_limit_scan.db"
    )

    router = RateLimitedRouter()
    notifier = RecordingNotifier()

    state = PortfolioState(
        total_value_gbp=10000,
        cash_gbp=400,
        positions=[],
    )

    runner = LiveRunner(
        db=db,
        t212=DummyT212(),
        router=router,
        ai=DisabledAIProvider(),
        notifier=notifier,
    )

    monkeypatch.setattr(
        runner,
        "portfolio",
        lambda: state,
    )

    try:
        result = runner.run()

        assert result is None
        assert router.calls > 0
        assert notifier.messages == []

        with db.session() as session:
            scans = list(
                session.scalars(
                    select(ScanRun)
                )
            )

            alerts = list(
                session.scalars(
                    select(AlertRecord)
                )
            )

        assert len(scans) == 1

        scan = scans[0]

        assert scan.status == "ok"
        assert scan.candidate_count == 0
        assert (
            scan.notification_sent
            is False
        )

        assert alerts == []

    finally:
        db.close()
