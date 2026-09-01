from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")


class Settings(BaseModel):
    app_env: str = os.getenv("APP_ENV", "development")
    tz: str = os.getenv("TZ", "Europe/London")
    trading212_env: str = os.getenv("TRADING212_ENV", "demo")
    trading212_api_key: str = os.getenv("TRADING212_API_KEY", "")
    trading212_api_secret: str = os.getenv("TRADING212_API_SECRET", "")
    twelve_data_api_key: str = os.getenv("TWELVE_DATA_API_KEY", "")
    ai_provider: str = os.getenv("AI_PROVIDER", "disabled")
    nvidia_api_key: str = os.getenv("NVIDIA_API_KEY", "")
    nvidia_model: str = os.getenv("NVIDIA_MODEL", "")
    nvidia_base_url: str = os.getenv(
        "NVIDIA_BASE_URL",
        "https://integrate.api.nvidia.com/v1",
    )
    openrouter_api_key: str = os.getenv("OPENROUTER_API_KEY", "")
    openrouter_model: str = os.getenv("OPENROUTER_MODEL", "")
    telegram_bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    telegram_chat_id: str = os.getenv("TELEGRAM_CHAT_ID", "")
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./portfolio_monitor.db")
    admin_token: str = os.getenv("ADMIN_TOKEN", "")
    dry_run: bool = os.getenv("DRY_RUN", "true").lower() in {"1", "true", "yes"}
    scheduler_enabled: bool = os.getenv("SCHEDULER_ENABLED", "false").lower() in {
        "1",
        "true",
        "yes",
    }
    scheduler_minute: int = int(os.getenv("SCHEDULER_MINUTE", "5"))
    scheduler_test_interval_seconds: int = int(
        os.getenv("SCHEDULER_TEST_INTERVAL_SECONDS", "0")
    )


def _load_yaml(name: str) -> dict[str, Any]:
    with (ROOT / "config" / name).open("r", encoding="utf-8") as file:
        return yaml.safe_load(file) or {}


@lru_cache
def get_settings() -> Settings:
    return Settings()


@lru_cache
def get_portfolio_config() -> dict[str, Any]:
    return _load_yaml("portfolio.yaml")


@lru_cache
def get_thresholds() -> dict[str, Any]:
    return _load_yaml("thresholds.yaml")


@lru_cache
def get_symbols() -> dict[str, Any]:
    return _load_yaml("symbols.yaml")


def _float_value(
    raw_value: Any,
    label: str,
    errors: list[str],
) -> float | None:
    try:
        return float(raw_value)
    except (TypeError, ValueError):
        errors.append(f"{label}: must be numeric")
        return None


def validate_config() -> list[str]:
    cfg = get_portfolio_config()
    thresholds = get_thresholds()
    symbols = get_symbols()
    errors: list[str] = []

    targets = cfg.get("targets", {})
    if not isinstance(targets, dict) or not targets:
        errors.append("targets must be a non-empty mapping")
        targets = {}

    numeric_targets: dict[str, float] = {}
    for symbol, raw_value in targets.items():
        name = str(symbol)
        value = _float_value(raw_value, f"targets.{name}", errors)
        if value is None:
            continue

        numeric_targets[name] = value
        if not 0 <= value <= 1:
            errors.append(f"targets.{name}: must be between 0 and 1")

    if abs(sum(numeric_targets.values()) - 1.0) > 1e-9:
        errors.append("targets must sum to 1.0")

    if str(cfg.get("account_currency", "GBP")).upper() != "GBP":
        errors.append("account_currency must be GBP in V1")

    hard_min_cash = _float_value(
        cfg.get("hard_min_cash_gbp", 0),
        "hard_min_cash_gbp",
        errors,
    )
    if hard_min_cash is not None and hard_min_cash < 0:
        errors.append("hard_min_cash_gbp must be >= 0")

    max_transition = _float_value(
        cfg.get("max_single_transition_pct", 0),
        "max_single_transition_pct",
        errors,
    )
    if max_transition is not None and not 0 < max_transition <= 1:
        errors.append("max_single_transition_pct must be > 0 and <= 1")

    desired_cash = _float_value(
        cfg.get("desired_cash_pct", 0),
        "desired_cash_pct",
        errors,
    )
    if desired_cash is not None:
        if not 0 <= desired_cash <= 1:
            errors.append("desired_cash_pct must be between 0 and 1")
        cash_target = numeric_targets.get("CASH")
        if cash_target is None:
            errors.append("targets.CASH is required")
        elif abs(cash_target - desired_cash) > 1e-9:
            errors.append("targets.CASH must equal desired_cash_pct")

    alert_cooldown = _float_value(
        cfg.get("alert_cooldown_hours", 0),
        "alert_cooldown_hours",
        errors,
    )
    if alert_cooldown is not None and alert_cooldown < 0:
        errors.append("alert_cooldown_hours must be >= 0")

    alert_validity = _float_value(
        cfg.get("alert_validity_hours", 0),
        "alert_validity_hours",
        errors,
    )
    if alert_validity is not None and alert_validity <= 0:
        errors.append("alert_validity_hours must be > 0")

    groups = cfg.get("groups", {}) or {}
    if not isinstance(groups, dict):
        errors.append("groups must be a mapping")
        groups = {}

    for group, members in groups.items():
        if group not in targets:
            errors.append(f"group {group} missing target")
        if not isinstance(members, list):
            errors.append(f"group {group}: members must be a list")
            continue
        for member in members:
            if member not in symbols:
                errors.append(f"group member {member} missing symbol mapping")

    for symbol in numeric_targets:
        if symbol == "CASH" or symbol in groups:
            continue
        if symbol not in symbols:
            errors.append(f"target {symbol}: missing symbol mapping")

    soft_targets = cfg.get("soft_component_targets", {}) or {}
    if not isinstance(soft_targets, dict):
        errors.append("soft_component_targets must be a mapping")
        soft_targets = {}

    numeric_soft_targets: dict[str, float] = {}
    for symbol, raw_value in soft_targets.items():
        name = str(symbol)
        value = _float_value(raw_value, f"soft_component_targets.{name}", errors)
        if value is None:
            continue
        numeric_soft_targets[name] = value
        if not 0 <= value <= 1:
            errors.append(f"soft_component_targets.{name}: must be between 0 and 1")
        if name not in symbols:
            errors.append(f"soft_component_targets.{name}: missing symbol mapping")

    priorities = cfg.get("strategic_priority", {}) or {}
    if not isinstance(priorities, dict):
        errors.append("strategic_priority must be a mapping")
        priorities = {}

    for symbol, raw_value in priorities.items():
        name = str(symbol)
        value = _float_value(raw_value, f"strategic_priority.{name}", errors)
        if value is None:
            continue
        if not 0 <= value <= 1:
            errors.append(f"strategic_priority.{name}: must be between 0 and 1")
        if name not in symbols and name not in groups:
            errors.append(f"strategic_priority.{name}: unknown symbol or group")

    quality_rank = cfg.get("quality_rank", {}) or {}
    if not isinstance(quality_rank, dict):
        errors.append("quality_rank must be a mapping")
    else:
        for symbol in quality_rank:
            if symbol not in symbols:
                errors.append(f"quality_rank.{symbol}: missing symbol mapping")

    for kind in ("pullback", "trim"):
        entries = thresholds.get(kind, {}) or {}
        if not isinstance(entries, dict):
            errors.append(f"{kind} thresholds must be a mapping")
            continue

        for symbol, values in entries.items():
            if symbol not in symbols:
                errors.append(f"{kind}.{symbol}: missing symbol mapping")

            if not isinstance(values, dict):
                errors.append(f"{kind}.{symbol}: malformed thresholds")
                continue

            try:
                watch = float(values["watch"])
                review = float(values["review"])
                strong = float(values["strong"])
            except (KeyError, TypeError, ValueError):
                errors.append(f"{kind}.{symbol}: malformed thresholds")
                continue

            if not (0 <= watch < review < strong <= 1):
                errors.append(
                    f"{kind}.{symbol}: require 0 <= watch < review < strong <= 1"
                )

            if kind == "pullback":
                abnormal = values.get("abnormal_day")
                if abnormal is not None:
                    abnormal_value = _float_value(
                        abnormal,
                        f"pullback.{symbol}.abnormal_day",
                        errors,
                    )
                    if abnormal_value is not None and not 0 < abnormal_value <= 1:
                        errors.append(
                            f"pullback.{symbol}.abnormal_day: must be > 0 and <= 1"
                        )

                if float(numeric_targets.get(symbol, 0)) <= 0:
                    errors.append(f"pullback.{symbol}: symbol needs a positive direct target")

            if kind == "trim":
                has_direct_target = symbol in numeric_targets
                has_soft_target = symbol in numeric_soft_targets
                if not has_direct_target and not has_soft_target:
                    errors.append(f"trim.{symbol}: symbol needs a target or soft target")

            meta = symbols.get(symbol)
            if isinstance(meta, dict):
                if not meta.get("exchange"):
                    errors.append(f"symbols.{symbol}: exchange is required")
                if not (meta.get("yahoo") or meta.get("twelve_data")):
                    errors.append(
                        f"symbols.{symbol}: configure yahoo or twelve_data market symbol"
                    )

    return errors
