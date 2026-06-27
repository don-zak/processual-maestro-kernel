from __future__ import annotations

import logging
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

try:
    import structlog

    _structlog_available = True
except Exception:
    _structlog_available = False


@dataclass
class LogEvent:
    event_type: str
    workflow_id: str | None = None
    agent_id: str | None = None
    fate_rank: str | None = None
    operation: str | None = None
    status: str = "info"
    latency_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class StructuredLogger:
    def __init__(self, name: str = "processual_maestro") -> None:
        self._name = name
        if _structlog_available:
            structlog.configure(
                processors=[
                    structlog.stdlib.filter_by_level,
                    structlog.stdlib.add_logger_name,
                    structlog.stdlib.add_log_level,
                    structlog.stdlib.PositionalArgumentsFormatter(),
                    structlog.processors.TimeStamper(fmt="iso"),
                    structlog.processors.JSONRenderer(),
                ],
                context_class=dict,
                logger_factory=structlog.PrintLoggerFactory(),
                cache_logger_on_first_use=True,
            )
            self._logger = structlog.get_logger(name)
        else:
            self._logger = logging.getLogger(name)
            handler = logging.StreamHandler(sys.stdout)
            handler.setFormatter(logging.Formatter("%(message)s"))
            self._logger.addHandler(handler)
            self._logger.setLevel(logging.INFO)

    def info(self, event: str, **kwargs: Any) -> None:
        if _structlog_available:
            self._logger.info(event, **kwargs)
        else:
            self._logger.info(f"{event} {kwargs}")

    def warning(self, event: str, **kwargs: Any) -> None:
        if _structlog_available:
            self._logger.warning(event, **kwargs)
        else:
            self._logger.warning(f"{event} {kwargs}")

    def error(self, event: str, **kwargs: Any) -> None:
        if _structlog_available:
            self._logger.error(event, **kwargs)
        else:
            self._logger.error(f"{event} {kwargs}")

    def log_event(self, log_event: LogEvent) -> None:
        base = {
            "event_type": log_event.event_type,
            "workflow_id": log_event.workflow_id,
            "agent_id": log_event.agent_id,
            "fate_rank": log_event.fate_rank,
            "operation": log_event.operation,
            "status": log_event.status,
            "latency_ms": log_event.latency_ms,
            "timestamp": log_event.timestamp,
        }
        base.update(log_event.metadata)
        self.info(log_event.event_type, **base)


_loggers: dict[str, StructuredLogger] = {}


def get_logger(name: str = "processual_maestro") -> StructuredLogger:
    if name not in _loggers:
        _loggers[name] = StructuredLogger(name)
    return _loggers[name]
