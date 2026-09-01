from __future__ import annotations

import logging
import threading
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from app.config import get_settings
from app.jobs.live import LiveRunner

log = logging.getLogger(__name__)

_stop = threading.Event()
_thread: threading.Thread | None = None


def _loop() -> None:
    s = get_settings()
    tz = ZoneInfo(s.tz)

    last_key: tuple[int, int, int, int] | None = None
    last_test_run = 0.0

    while not _stop.is_set():
        now = datetime.now(tz)
        should_run = False

        if s.scheduler_test_interval_seconds > 0:
            current = time.monotonic()
            if current - last_test_run >= s.scheduler_test_interval_seconds:
                last_test_run = current
                should_run = True
        else:
            key = (
                now.year,
                now.timetuple().tm_yday,
                now.hour,
                now.minute,
            )
            if now.minute == s.scheduler_minute and key != last_key:
                last_key = key
                should_run = True

        if should_run:
            try:
                LiveRunner().run()
            except Exception:
                log.exception("scheduled scan failed")

        _stop.wait(5)


def start_scheduler() -> threading.Thread | None:
    global _thread

    s = get_settings()

    if not s.scheduler_enabled:
        return None

    if _thread and _thread.is_alive():
        return _thread

    _stop.clear()

    _thread = threading.Thread(
        target=_loop,
        name="portfolio-hourly-scheduler",
        daemon=True,
    )
    _thread.start()

    log.info(
        "scheduler started: minute=%s test_interval=%ss timezone=%s",
        s.scheduler_minute,
        s.scheduler_test_interval_seconds,
        s.tz,
    )

    return _thread


def stop_scheduler() -> None:
    _stop.set()
