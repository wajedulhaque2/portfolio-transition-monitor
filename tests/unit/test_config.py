from app import config


def base_portfolio() -> dict:
    return {
        "account_currency": "GBP",
        "hard_min_cash_gbp": 100,
        "desired_cash_pct": 0.10,
        "max_single_transition_pct": 0.015,
        "alert_cooldown_hours": 12,
        "alert_validity_hours": 4,
        "targets": {"ABC": 0.90, "CASH": 0.10},
        "groups": {},
        "soft_component_targets": {},
        "quality_rank": {},
        "strategic_priority": {"ABC": 0.8},
    }


def test_config_valid_and_targets_sum():
    assert config.validate_config() == []
    assert abs(sum(config.get_portfolio_config()["targets"].values()) - 1.0) < 1e-9


def test_validation_rejects_missing_market_mapping(monkeypatch):
    portfolio = base_portfolio()
    thresholds = {
        "pullback": {
            "ABC": {
                "watch": 0.05,
                "review": 0.08,
                "strong": 0.12,
                "abnormal_day": 0.15,
            }
        },
        "trim": {},
    }

    monkeypatch.setattr(config, "get_portfolio_config", lambda: portfolio)
    monkeypatch.setattr(config, "get_thresholds", lambda: thresholds)
    monkeypatch.setattr(config, "get_symbols", dict)

    errors = config.validate_config()

    assert "pullback.ABC: missing symbol mapping" in errors


def test_validation_rejects_non_gbp_and_cash_mismatch(monkeypatch):
    portfolio = base_portfolio()
    portfolio["account_currency"] = "EUR"
    portfolio["desired_cash_pct"] = 0.05

    monkeypatch.setattr(config, "get_portfolio_config", lambda: portfolio)
    monkeypatch.setattr(config, "get_thresholds", lambda: {"pullback": {}, "trim": {}})
    monkeypatch.setattr(config, "get_symbols", dict)

    errors = config.validate_config()

    assert "account_currency must be GBP in V1" in errors
    assert "targets.CASH must equal desired_cash_pct" in errors


def test_validation_rejects_pullback_without_direct_target(monkeypatch):
    portfolio = base_portfolio()
    portfolio["targets"] = {"CORE": 0.90, "CASH": 0.10}
    portfolio["groups"] = {"CORE": ["ABC"]}
    portfolio["soft_component_targets"] = {"ABC": 0.90}
    portfolio["strategic_priority"] = {"ABC": 1.0}

    thresholds = {
        "pullback": {
            "ABC": {
                "watch": 0.05,
                "review": 0.08,
                "strong": 0.12,
            }
        },
        "trim": {},
    }
    symbols = {
        "ABC": {
            "trading212": None,
            "yahoo": "ABC",
            "twelve_data": None,
            "exchange": "NASDAQ",
            "currency": "USD",
        }
    }

    monkeypatch.setattr(config, "get_portfolio_config", lambda: portfolio)
    monkeypatch.setattr(config, "get_thresholds", lambda: thresholds)
    monkeypatch.setattr(config, "get_symbols", lambda: symbols)

    errors = config.validate_config()

    assert "pullback.ABC: symbol needs a positive direct target" in errors


def test_validation_accepts_zero_target_for_trim(monkeypatch):
    portfolio = base_portfolio()
    portfolio["targets"] = {"ABC": 0.0, "KEEP": 0.90, "CASH": 0.10}
    portfolio["strategic_priority"] = {"ABC": 1.0, "KEEP": 0.5}

    thresholds = {
        "pullback": {},
        "trim": {
            "ABC": {
                "watch": 0.05,
                "review": 0.10,
                "strong": 0.15,
            }
        },
    }
    symbols = {
        "ABC": {
            "trading212": None,
            "yahoo": "ABC",
            "twelve_data": None,
            "exchange": "NASDAQ",
            "currency": "USD",
        },
        "KEEP": {
            "trading212": None,
            "yahoo": "KEEP",
            "twelve_data": None,
            "exchange": "NASDAQ",
            "currency": "USD",
        },
    }

    monkeypatch.setattr(config, "get_portfolio_config", lambda: portfolio)
    monkeypatch.setattr(config, "get_thresholds", lambda: thresholds)
    monkeypatch.setattr(config, "get_symbols", lambda: symbols)

    assert config.validate_config() == []
