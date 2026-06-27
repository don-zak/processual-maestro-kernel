from __future__ import annotations

import os
from typing import Any

SENTRY_DSN: str | None = None


def init_sentry(dsn: str | None = None, environment: str = "development", release: str = "2.0.0") -> bool:
    global SENTRY_DSN
    dsn = dsn or os.environ.get("SENTRY_DSN")
    if not dsn:
        return False
    SENTRY_DSN = dsn
    try:
        import sentry_sdk

        sentry_sdk.init(
            dsn=dsn,
            environment=environment,
            release=release,
            traces_sample_rate=float(os.environ.get("SENTRY_TRACES_SAMPLE_RATE", "0.1")),
        )
        return True
    except Exception:
        return False


def capture_exception(exc: Exception, extra: dict[str, Any] | None = None) -> None:
    if SENTRY_DSN is None:
        return
    try:
        import sentry_sdk

        with sentry_sdk.push_scope() as scope:
            if extra:
                for key, value in extra.items():
                    scope.set_extra(key, value)
            sentry_sdk.capture_exception(exc)
    except Exception:
        pass  # nosec


def capture_message(message: str, level: str = "info", extra: dict[str, Any] | None = None) -> None:
    if SENTRY_DSN is None:
        return
    try:
        import sentry_sdk

        with sentry_sdk.push_scope() as scope:
            if extra:
                for key, value in extra.items():
                    scope.set_extra(key, value)
            sentry_sdk.capture_message(message, level=level)
    except Exception:
        pass  # nosec
