from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import (
    FastAPI,
    Header,
    HTTPException,
)

from app.config import (
    get_settings,
    validate_config,
)
from app.db.session import Database
from app.jobs.live import LiveRunner
from app.logging import configure_logging
from app.scheduler import (
    start_scheduler,
    stop_scheduler,
)

configure_logging()


@asynccontextmanager
async def lifespan(
    app: FastAPI,
):
    del app

    settings = get_settings()

    Database(
        settings.database_url
    ).init()

    start_scheduler()

    try:
        yield

    finally:
        stop_scheduler()


app = FastAPI(
    title="Portfolio Transition Monitor",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/healthz")
def healthz() -> dict:
    return {
        "status": "ok"
    }


@app.get("/readyz")
def readyz() -> dict:
    errors = validate_config()
    settings = get_settings()

    ready = (
        not errors
        and bool(
            settings.database_url
        )
    )

    if not ready:
        raise HTTPException(
            503,
            detail=(
                errors
                or [
                    "database not configured"
                ]
            ),
        )

    return {
        "status": "ready",
        "dry_run": settings.dry_run,
        "ai_provider":
            settings.ai_provider,
    }


@app.post("/admin/run-scan")
def run_scan(
    x_admin_token: str | None = Header(
        default=None
    ),
) -> dict:
    settings = get_settings()

    if (
        not settings.admin_token
        or x_admin_token
        != settings.admin_token
    ):
        raise HTTPException(
            401,
            detail="unauthorized",
        )

    rec = LiveRunner().run()

    return {
        "status": "ok",
        "candidate": (
            None
            if rec is None
            else {
                "action": rec.action,
                "buy": rec.buy_symbol,
                "sell": rec.sell_symbol,
                "amount_gbp":
                    rec.amount_gbp,
                "score": rec.score,
            }
        ),
    }