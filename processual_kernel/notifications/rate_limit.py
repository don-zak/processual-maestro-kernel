from __future__ import annotations

import os
import time


class RateLimiter:
    def __init__(self) -> None:
        self._last_send: float = 0.0
        self._interval: float = float(os.environ.get("DISCORD_RATE_LIMIT_SECONDS", "30"))

    def allow(self) -> bool:
        now = time.time()
        if now - self._last_send >= self._interval:
            self._last_send = now
            return True
        return False

    def reset(self) -> None:
        self._last_send = 0.0
