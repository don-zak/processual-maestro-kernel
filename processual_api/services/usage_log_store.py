from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_USAGE_LOG_PATH = _DATA_DIR / "usage_logs.jsonl"


def append_usage_log(record: dict[str, Any]) -> None:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)

    clean_record = {
        "created_at": record.get("created_at") or datetime.now(UTC).isoformat(),
        "request_id": record.get("request_id", ""),
        "client_id": record.get("client_id", ""),
        "user_id": record.get("user_id", ""),
        "api_key_id": record.get("api_key_id", ""),
        "api_key_prefix": record.get("api_key_prefix", ""),
        "auth_method": record.get("auth_method", ""),
        "session_type": record.get("session_type", ""),
        "method": record.get("method", ""),
        "endpoint": record.get("endpoint", ""),
        "status_code": record.get("status_code", 0),
        "latency_ms": record.get("latency_ms", 0),
        "role": record.get("role", ""),
    }

    with _USAGE_LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(clean_record, ensure_ascii=False) + "\n")
