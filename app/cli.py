from __future__ import annotations

import json
import secrets

import typer
import yaml

from app.ai.arbiter import safe_decide
from app.ai.base import DisabledAIProvider
from app.config import (
    ROOT,
    get_settings,
    get_symbols,
    validate_config,
)
from app.db.session import Database
from app.jobs.live import (
    LiveRunner,
    ProviderRouter,
    make_ai,
)
from app.logging import configure_logging
from app.market_data.twelve_data import (
    TwelveDataProvider,
)
from app.notifications.telegram import (
    TelegramNotifier,
)
from app.trading212.client import (
    Trading212Client,
)
from app.trading212.mapper import map_state

configure_logging()

app = typer.Typer(
    no_args_is_help=True
)


@app.command("validate-config")
def validate() -> None:
    errors = validate_config()

    if errors:
        for error in errors:
            typer.echo(
                f"ERROR: {error}"
            )

        raise typer.Exit(1)

    typer.echo(
        "Configuration valid. "
        "Targets total 100.00%"
    )


@app.command("init-db")
def init_db() -> None:
    settings = get_settings()

    db = Database(
        settings.database_url
    )

    try:
        db.init()

    finally:
        db.close()

    typer.echo(
        "Database initialized"
    )


@app.command("run-scan")
def run_scan() -> None:
    rec = LiveRunner().run()

    if not rec:
        typer.echo(
            "NO ACTION"
        )

        return

    typer.echo(
        json.dumps(
            {
                "action":
                    rec.action,
                "buy":
                    rec.buy_symbol,
                "sell":
                    rec.sell_symbol,
                "amount_gbp":
                    rec.amount_gbp,
                "score":
                    rec.score,
                "tier":
                    rec.tier,
            },
            indent=2,
        )
    )


@app.command("test-notification")
def test_notification() -> None:
    settings = get_settings()

    if (
        not settings.telegram_bot_token
        or not settings.telegram_chat_id
    ):
        raise typer.BadParameter(
            "TELEGRAM_BOT_TOKEN and "
            "TELEGRAM_CHAT_ID required"
        )

    notifier = TelegramNotifier(
        settings.telegram_bot_token,
        settings.telegram_chat_id,
    )

    try:
        notifier.send(
            "Portfolio Monitor test "
            "notification. DRY RUN advisory "
            "mode; no trade placed."
        )

    finally:
        client = getattr(
            notifier,
            "client",
            None,
        )

        if client is not None:
            client.close()

    typer.echo(
        "Telegram test sent"
    )


@app.command("smoke-test")
def smoke_test() -> None:
    settings = get_settings()

    if (
        not settings.trading212_api_key
        or not settings.trading212_api_secret
    ):
        raise typer.BadParameter(
            "Trading 212 read-only "
            "credentials required"
        )

    client = Trading212Client(
        settings.trading212_api_key,
        settings.trading212_api_secret,
        settings.trading212_env,
    )

    try:
        summary = (
            client.account_summary()
        )

        positions = (
            client.positions()
        )

        orders = (
            client.orders()
        )

        ticker_map = {
            str(
                meta["trading212"]
            ): symbol
            for symbol, meta
            in get_symbols().items()
            if meta.get(
                "trading212"
            )
        }

        state = map_state(
            summary,
            positions,
            orders,
            ticker_map,
        )

        typer.echo(
            json.dumps(
                {
                    "trading212":
                        "PASS",
                    "account_total_gbp":
                        round(
                            state.total_value_gbp,
                            2,
                        ),
                    "cash_gbp":
                        round(
                            state.cash_gbp,
                            2,
                        ),
                    "positions_count":
                        len(
                            state.positions
                        ),
                    "positions": [
                        {
                            "symbol":
                                position.symbol,
                            "quantity":
                                position.quantity,
                            "value_gbp":
                                round(
                                    position.value_gbp,
                                    2,
                                ),
                        }
                        for position
                        in state.positions
                    ],
                    "pending_buy_symbols":
                        sorted(
                            state.pending_buy_symbols
                        ),
                    "orders_count":
                        len(
                            orders
                            or []
                        ),
                    "order_placement_implemented":
                        False,
                    "dry_run":
                        settings.dry_run,
                },
                indent=2,
            )
        )

    finally:
        http_client = getattr(
            client,
            "client",
            None,
        )

        if http_client is not None:
            http_client.close()


@app.command("resolve-symbols")
def resolve_symbols(
    write: bool = typer.Option(
        False,
        "--write",
    ),
) -> None:
    settings = get_settings()

    if (
        not settings.trading212_api_key
        or not settings.trading212_api_secret
    ):
        raise typer.BadParameter(
            "Trading 212 credentials "
            "required"
        )

    client = Trading212Client(
        settings.trading212_api_key,
        settings.trading212_api_secret,
        settings.trading212_env,
    )

    try:
        instruments = (
            client.instruments()
            or []
        )

    finally:
        http_client = getattr(
            client,
            "client",
            None,
        )

        if http_client is not None:
            http_client.close()

    existing = (
        get_symbols().copy()
    )

    names = {
        symbol.upper(): symbol
        for symbol in existing
    }

    updates = 0

    for item in instruments:
        if not isinstance(
            item,
            dict,
        ):
            continue

        ticker = str(
            item.get("ticker")
            or item.get("shortName")
            or ""
        )

        raw_name = str(
            item.get("name")
            or ""
        ).upper()

        ticker_upper = (
            ticker.upper()
        )

        ticker_root = (
            ticker_upper.split(
                "_",
                1,
            )[0]
        )

        for needle, internal in names.items():
            if (
                ticker_upper
                == needle
                or ticker_root
                == needle
                or ticker_upper.startswith(
                    needle + "_"
                )
                or raw_name.startswith(
                    needle + " "
                )
            ) and not existing[
                internal
            ].get(
                "trading212"
            ):
                existing[
                    internal
                ][
                    "trading212"
                ] = ticker

                updates += 1

    typer.echo(
        yaml.safe_dump(
            existing,
            sort_keys=False,
        )
    )

    if write:
        (
            ROOT
            / "config"
            / "symbols.yaml"
        ).write_text(
            yaml.safe_dump(
                existing,
                sort_keys=False,
            ),
            encoding="utf-8",
        )

        typer.echo(
            f"Wrote mappings "
            f"({updates} updates). "
            "Review before trusting "
            "live scans."
        )


@app.command("test-market-data")
def test_market_data(
    symbol: str = typer.Option(
        "GOOGL",
        "--symbol",
    ),
) -> None:
    settings = get_settings()

    meta = get_symbols().get(
        symbol.upper()
    )

    if not meta:
        raise typer.BadParameter(
            "Unknown internal symbol: "
            f"{symbol}"
        )

    twelve = (
        TwelveDataProvider(
            settings.twelve_data_api_key
        )
        if settings.twelve_data_api_key
        else None
    )

    router = ProviderRouter(
        twelve
    )

    try:
        source, quote, bars = (
            router.fetch(
                meta
            )
        )

        typer.echo(
            json.dumps(
                {
                    "source":
                        source,
                    "symbol":
                        symbol.upper(),
                    "price":
                        quote.price,
                    "currency":
                        quote.currency,
                    "quote_timestamp":
                        quote.timestamp.isoformat(),
                    "daily_bars":
                        len(
                            bars
                        ),
                    "latest_bar":
                        (
                            bars[-1]
                            .date
                            .isoformat()
                            if bars
                            else None
                        ),
                },
                indent=2,
            )
        )

    finally:
        if twelve is not None:
            twelve.client.close()

        yahoo = getattr(
            router,
            "yahoo",
            None,
        )

        yahoo_client = getattr(
            yahoo,
            "client",
            None,
        )

        if yahoo_client is not None:
            yahoo_client.close()


@app.command("test-ai")
def test_ai() -> None:
    provider = make_ai()

    if isinstance(
        provider,
        DisabledAIProvider,
    ):
        raise typer.BadParameter(
            "AI is disabled or provider "
            "credentials/model are "
            "incomplete"
        )

    payload = {
        "candidate": {
            "action":
                "ROTATE",
            "buy_symbol":
                "GOOGL",
            "sell_symbol":
                "AAPL",
            "amount_gbp":
                100,
            "score":
                88,
            "tier":
                "STRONG",
            "reason":
                "Synthetic connectivity "
                "test only",
        }
    }

    try:
        decision = safe_decide(
            provider,
            payload,
            100,
            False,
        )

        typer.echo(
            decision.model_dump_json(
                indent=2
            )
        )

    finally:
        providers = getattr(
            provider,
            "providers",
            [provider],
        )

        for item in providers:
            client = getattr(
                item,
                "client",
                None,
            )

            if client is not None:
                client.close()


@app.command("generate-admin-token")
def generate_admin_token() -> None:
    typer.echo(
        secrets.token_urlsafe(
            32
        )
    )
