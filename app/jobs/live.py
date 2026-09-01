
from __future__ import annotations

import logging
import uuid
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select

from app.ai.arbiter import safe_decide
from app.ai.base import AIProvider, DisabledAIProvider, FallbackAIProvider
from app.ai.nvidia import NvidiaProvider
from app.ai.openrouter import OpenRouterProvider
from app.config import (
    get_portfolio_config,
    get_settings,
    get_symbols,
    get_thresholds,
)
from app.db.locks import release_lock, try_acquire_lock
from app.db.models import PortfolioSnapshot, PositionSnapshot, ScanRun
from app.db.session import Database
from app.jobs.scan import (
    MonitorEngine,
    Recommendation,
    format_alert,
    record_alert,
    should_notify,
)
from app.market_data.base import DailyBar, MarketDataProvider, Quote
from app.market_data.freshness import (
    is_quote_fresh,
    latest_completed_session_date,
)
from app.market_data.history_cache import HistoryCache
from app.market_data.twelve_data import TwelveDataProvider
from app.market_data.yahoo import YahooProvider
from app.notifications.base import Notifier, NullNotifier
from app.notifications.telegram import TelegramNotifier
from app.portfolio.models import MarketMetrics, PortfolioState
from app.signals.metrics import compute_market_metrics
from app.trading212.client import Trading212Client
from app.trading212.mapper import map_state

log = logging.getLogger(__name__)


def make_ai() -> AIProvider:
    settings = get_settings()
    providers: list[AIProvider] = []

    if (
        settings.ai_provider in {"nvidia", "auto"}
        and settings.nvidia_api_key
        and settings.nvidia_model
    ):
        providers.append(
            NvidiaProvider(
                settings.nvidia_api_key,
                settings.nvidia_model,
                settings.nvidia_base_url,
            )
        )

    if (
        settings.ai_provider in {"openrouter", "auto"}
        and settings.openrouter_api_key
        and settings.openrouter_model
    ):
        providers.append(
            OpenRouterProvider(
                settings.openrouter_api_key,
                settings.openrouter_model,
            )
        )

    if not providers:
        return DisabledAIProvider()

    if len(providers) == 1:
        return providers[0]

    return FallbackAIProvider(providers)


def make_notifier() -> Notifier:
    settings = get_settings()

    if settings.telegram_bot_token and settings.telegram_chat_id:
        return TelegramNotifier(
            settings.telegram_bot_token,
            settings.telegram_chat_id,
        )

    return NullNotifier()


class ProviderRouter:
    def __init__(
        self,
        twelve: MarketDataProvider | None,
        yahoo: MarketDataProvider | None = None,
        history_cache: HistoryCache | None = None,
    ):
        self.twelve = twelve
        self.yahoo = yahoo or YahooProvider()
        self.history_cache = history_cache

    def _history(
        self,
        *,
        source: str,
        provider: MarketDataProvider,
        symbol: str,
        exchange: str,
        now: datetime,
    ) -> list[DailyBar]:
        if self.history_cache is None:
            return provider.history(symbol)

        required_through = latest_completed_session_date(
            exchange,
            now=now,
        )

        if required_through is None:
            raise RuntimeError(
                f"unsupported exchange for history cache: {exchange}"
            )

        cached = self.history_cache.get(
            source,
            symbol,
            required_through,
        )

        if cached is not None:
            log.info(
                "history cache hit: source=%s symbol=%s through=%s",
                source,
                symbol,
                required_through.isoformat(),
            )
            return cached

        log.info(
            "history cache refresh: source=%s symbol=%s through=%s",
            source,
            symbol,
            required_through.isoformat(),
        )

        downloaded = provider.history(symbol)

        stored = self.history_cache.put(
            source,
            symbol,
            downloaded,
            completed_through=required_through,
            now=now,
        )

        if stored[-1].date < required_through:
            raise RuntimeError(
                "history does not include latest completed session"
            )

        return stored

    def _fetch_provider(
        self,
        *,
        source: str,
        provider: MarketDataProvider,
        symbol: str,
        exchange: str,
        now: datetime,
    ) -> tuple[str, Quote, list[DailyBar]]:
        quote = provider.quote(symbol)

        bars = self._history(
            source=source,
            provider=provider,
            symbol=symbol,
            exchange=exchange,
            now=now,
        )

        return (
            source,
            quote,
            bars,
        )

    def fetch(
        self,
        meta: dict[str, Any],
        *,
        now: datetime | None = None,
    ) -> tuple[str, Quote, list[DailyBar]]:
        fetch_time = now or datetime.now(UTC)

        exchange = str(
            meta.get("exchange") or ""
        )

        yahoo_symbol = meta.get("yahoo")

        if yahoo_symbol:
            try:
                return self._fetch_provider(
                    source="yahoo",
                    provider=self.yahoo,
                    symbol=str(yahoo_symbol),
                    exchange=exchange,
                    now=fetch_time,
                )

            except Exception as exc:  # noqa: BLE001 - provider fallback boundary
                log.warning(
                    "Yahoo failed for %s: %s",
                    yahoo_symbol,
                    type(exc).__name__,
                )

        twelve_symbol = meta.get(
            "twelve_data"
        )

        if (
            self.twelve is not None
            and twelve_symbol
        ):
            try:
                return self._fetch_provider(
                    source="twelve_data",
                    provider=self.twelve,
                    symbol=str(twelve_symbol),
                    exchange=exchange,
                    now=fetch_time,
                )

            except Exception as exc:  # noqa: BLE001 - provider fallback boundary
                log.warning(
                    "Twelve Data failed for %s: %s",
                    twelve_symbol,
                    type(exc).__name__,
                )

        raise RuntimeError(
            "no usable market data source"
        )


class LiveRunner:
    def __init__(
        self,
        db: Database | None = None,
        t212: Trading212Client | None = None,
        router: ProviderRouter | None = None,
        ai: AIProvider | None = None,
        notifier: Notifier | None = None,
    ):
        self.settings = get_settings()
        self.cfg = get_portfolio_config()
        self.thresholds = get_thresholds()
        self.symbols = get_symbols()

        self._owns_db = db is None

        self.db = (
            db
            or Database(
                self.settings.database_url
            )
        )

        self.db.init()

        self.history_cache = HistoryCache(
            self.db
        )

        self.t212 = (
            t212
            or Trading212Client(
                self.settings.trading212_api_key,
                self.settings.trading212_api_secret,
                self.settings.trading212_env,
            )
        )

        self.router = (
            router
            or ProviderRouter(
                TwelveDataProvider(
                    self.settings.twelve_data_api_key
                )
                if self.settings.twelve_data_api_key
                else None,
                history_cache=self.history_cache,
            )
        )

        self.ai = (
            ai
            or make_ai()
        )

        self.notifier = (
            notifier
            or make_notifier()
        )

        self.engine = MonitorEngine(
            self.cfg,
            self.thresholds,
        )

    def ticker_map(
        self,
    ) -> dict[str, str]:
        return {
            str(meta["trading212"]): symbol
            for symbol, meta in self.symbols.items()
            if meta.get("trading212")
        }

    def portfolio(
        self,
    ) -> PortfolioState:
        return map_state(
            self.t212.account_summary(),
            self.t212.positions(),
            self.t212.orders(),
            self.ticker_map(),
        )

    def persist_portfolio(
        self,
        state: PortfolioState,
    ) -> None:
        with self.db.session() as session:
            session.add(
                PortfolioSnapshot(
                    total_value_gbp=state.total_value_gbp,
                    cash_gbp=state.cash_gbp,
                )
            )

            for position in state.positions:
                session.add(
                    PositionSnapshot(
                        symbol=position.symbol,
                        quantity=position.quantity,
                        value_gbp=position.value_gbp,
                        average_price=position.average_price,
                        pnl_gbp=position.pnl_gbp,
                    )
                )

            session.commit()

    def market_metrics(
        self,
        state: PortfolioState,
    ) -> dict[str, MarketMetrics]:
        del state

        wanted = (
            set(
                self.thresholds.get(
                    "pullback",
                    {},
                )
            )
            | set(
                self.thresholds.get(
                    "trim",
                    {},
                )
            )
        )

        output: dict[
            str,
            MarketMetrics,
        ] = {}

        scan_time = datetime.now(UTC)

        for symbol in sorted(wanted):
            meta = self.symbols.get(
                symbol
            )

            if not meta:
                continue

            try:
                source, quote, bars = (
                    self.router.fetch(
                        meta,
                        now=scan_time,
                    )
                )

                exchange = str(
                    meta.get(
                        "exchange"
                    )
                    or ""
                )

                fresh = is_quote_fresh(
                    exchange,
                    quote.timestamp,
                    now=scan_time,
                )

                if not fresh:
                    log.info(
                        "market data stale for %s "
                        "(source=%s exchange=%s timestamp=%s)",
                        symbol,
                        source,
                        exchange,
                        quote.timestamp.isoformat(),
                    )

                output[symbol] = (
                    compute_market_metrics(
                        symbol,
                        quote,
                        bars,
                        fresh=fresh,
                    )
                )

            except Exception as exc:  # noqa: BLE001 - one symbol must not abort scan
                log.warning(
                    "market data unavailable for %s: %s",
                    symbol,
                    type(exc).__name__,
                )

        return output

    def run(
        self,
    ) -> Recommendation | None:
        if not try_acquire_lock(
            self.db
        ):
            log.info(
                "scan skipped: lock held"
            )

            if self._owns_db:
                self.db.close()

            return None

        scan_id = uuid.uuid4().hex

        with self.db.session() as session:
            session.add(
                ScanRun(
                    scan_id=scan_id,
                )
            )

            session.commit()

        try:
            state = self.portfolio()

            self.persist_portfolio(
                state
            )

            market_metrics = (
                self.market_metrics(
                    state
                )
            )

            recommendations = (
                self.engine.evaluate(
                    state,
                    market_metrics,
                )
            )

            recommendation = (
                recommendations[0]
                if recommendations
                else None
            )

            notification_sent = False

            if (
                recommendation
                and should_notify(
                    self.db,
                    recommendation,
                    int(
                        self.cfg.get(
                            "alert_cooldown_hours",
                            12,
                        )
                    ),
                )
            ):
                if recommendation.manual_review:
                    final = recommendation

                elif (
                    recommendation.score
                    >= 75
                    and self.settings.ai_provider
                    != "disabled"
                ):
                    decision = safe_decide(
                        self.ai,
                        {
                            "candidate": asdict(
                                recommendation
                            )
                        },
                        recommendation.amount_gbp,
                        recommendation.manual_review,
                    )

                    if (
                        decision.decision
                        == "NO_ACTION"
                    ):
                        final = None

                    elif (
                        decision.decision
                        == "MANUAL_REVIEW"
                    ):
                        final = Recommendation(
                            "MANUAL_REVIEW",
                            recommendation.buy_symbol,
                            recommendation.sell_symbol,
                            0,
                            recommendation.score,
                            recommendation.tier,
                            decision.reason,
                            True,
                        )

                    else:
                        recommendation.amount_gbp = min(
                            recommendation.amount_gbp,
                            decision.amount_gbp,
                        )

                        final = (
                            recommendation
                            if recommendation.amount_gbp
                            > 0
                            else None
                        )

                else:
                    final = recommendation

                if final:
                    message = format_alert(
                        final,
                        state,
                        market_metrics,
                        self.settings.dry_run,
                    )

                    self.notifier.send(
                        message
                    )

                    record_alert(
                        self.db,
                        final,
                        message,
                    )

                    notification_sent = True

            with self.db.session() as session:
                row = session.scalar(
                    select(
                        ScanRun
                    ).where(
                        ScanRun.scan_id
                        == scan_id
                    )
                )

                row.status = "ok"
                row.finished_at = (
                    datetime.now(UTC)
                )
                row.candidate_count = len(
                    recommendations
                )
                row.notification_sent = (
                    notification_sent
                )

                session.commit()

            return recommendation

        except Exception as exc:
            with self.db.session() as session:
                row = session.scalar(
                    select(
                        ScanRun
                    ).where(
                        ScanRun.scan_id
                        == scan_id
                    )
                )

                row.status = "error"
                row.detail = type(
                    exc
                ).__name__
                row.finished_at = (
                    datetime.now(UTC)
                )

                session.commit()

            raise

        finally:
            try:
                release_lock(
                    self.db
                )

            finally:
                if self._owns_db:
                    self.db.close()