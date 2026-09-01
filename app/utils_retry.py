from __future__ import annotations

import time
from collections.abc import Callable


def retry_call[T](fn: Callable[[], T], attempts: int = 3, base_delay: float = 0.5) -> T:
    last: Exception | None = None
    for i in range(attempts):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 - bounded retry wrapper intentionally handles provider errors
            last = exc
            if i < attempts - 1:
                time.sleep(base_delay * (2**i))
    assert last is not None
    raise last
