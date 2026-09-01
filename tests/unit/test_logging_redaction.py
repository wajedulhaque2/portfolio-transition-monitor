from __future__ import annotations

import logging

from app.logging import (
    SECRET_ENV_KEYS,
    SecretRedactionFilter,
)


def test_secret_filter_redacts_all_configured_secrets(
    monkeypatch,
):
    secrets = {}

    for index, key in enumerate(
        SECRET_ENV_KEYS,
    ):
        value = (
            f"super-secret-value-{index}"
        )

        secrets[key] = value

        monkeypatch.setenv(
            key,
            value,
        )

    message = " ".join(
        secrets.values()
    )

    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg=message,
        args=(),
        exc_info=None,
    )

    result = (
        SecretRedactionFilter()
        .filter(record)
    )

    assert result is True

    rendered = (
        record.getMessage()
    )

    for secret in secrets.values():
        assert secret not in rendered

    assert (
        rendered.count(
            "[REDACTED]"
        )
        == len(
            SECRET_ENV_KEYS
        )
    )


def test_secret_filter_redacts_formatted_arguments(
    monkeypatch,
):
    secret = (
        "argument-secret-value"
    )

    monkeypatch.setenv(
        "ADMIN_TOKEN",
        secret,
    )

    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="token=%s",
        args=(secret,),
        exc_info=None,
    )

    SecretRedactionFilter().filter(
        record
    )

    assert (
        record.getMessage()
        == "token=[REDACTED]"
    )

    assert record.args == ()


def test_secret_filter_leaves_normal_text_unchanged(
    monkeypatch,
):
    for key in SECRET_ENV_KEYS:
        monkeypatch.delenv(
            key,
            raising=False,
        )

    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="ordinary safe log message",
        args=(),
        exc_info=None,
    )

    SecretRedactionFilter().filter(
        record
    )

    assert (
        record.getMessage()
        == "ordinary safe log message"
    )
