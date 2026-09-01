from __future__ import annotations

import logging
import os

SECRET_ENV_KEYS = (
    "TRADING212_API_KEY",
    "TRADING212_API_SECRET",
    "TWELVE_DATA_API_KEY",
    "NVIDIA_API_KEY",
    "OPENROUTER_API_KEY",
    "TELEGRAM_BOT_TOKEN",
    "ADMIN_TOKEN",
)


class SecretRedactionFilter(logging.Filter):
    def filter(
        self,
        record: logging.LogRecord,
    ) -> bool:
        text = record.getMessage()

        for key in SECRET_ENV_KEYS:
            secret = os.getenv(
                key,
                "",
            )

            if secret:
                text = text.replace(
                    secret,
                    "[REDACTED]",
                )

        record.msg = text
        record.args = ()

        return True


def _add_redaction_filter(
    log_handler: logging.Handler,
) -> None:
    if any(
        isinstance(
            existing,
            SecretRedactionFilter,
        )
        for existing in log_handler.filters
    ):
        return

    log_handler.addFilter(
        SecretRedactionFilter()
    )


def configure_logging() -> None:
    root = logging.getLogger()

    if not root.handlers:
        stream_handler = (
            logging.StreamHandler()
        )

        stream_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)s "
                "%(name)s %(message)s"
            )
        )

        root.addHandler(
            stream_handler
        )

        root.setLevel(
            logging.INFO
        )

    for root_handler in root.handlers:
        _add_redaction_filter(
            root_handler
        )

    for logger_name in (
        "uvicorn",
        "uvicorn.error",
        "uvicorn.access",
    ):
        logger = logging.getLogger(
            logger_name
        )

        for uvicorn_handler in logger.handlers:
            _add_redaction_filter(
                uvicorn_handler
            )