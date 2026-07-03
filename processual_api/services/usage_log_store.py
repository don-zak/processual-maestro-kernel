from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..billing.usage_pricing import pricing_decision

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_USAGE_LOG_PATH = _DATA_DIR / "usage_logs.jsonl"
_RAW_API_KEY_PATTERN = re.compile(r"pmk_[A-Za-z0-9_-]+")


def sanitize_usage_endpoint(endpoint: str) -> str:
    return _RAW_API_KEY_PATTERN.sub("pmk_[redacted]", endpoint)


def append_usage_log(record: dict[str, Any]) -> None:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)

    endpoint = sanitize_usage_endpoint(str(record.get("endpoint", "")))
    pricing_record = pricing_decision(endpoint).to_usage_record()

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
        "endpoint": endpoint,
        "status_code": record.get("status_code", 0),
        "latency_ms": record.get("latency_ms", 0),
        "role": record.get("role", ""),
        "pricing_version": (
            record.get("pricing_version") or pricing_record["pricing_version"]
        ),
        "billing_policy": (
            record.get("billing_policy") or pricing_record["billing_policy"]
        ),
        "billing_scope": (
            record.get("billing_scope") or pricing_record["billing_scope"]
        ),
        "provider_cost_included": bool(
            record.get(
                "provider_cost_included",
                pricing_record["provider_cost_included"],
            )
        ),
        "endpoint_class": (
            record.get("endpoint_class") or pricing_record["endpoint_class"]
        ),
        "units_charged": int(
            record.get("units_charged", pricing_record["units_charged"]) or 0
        ),
    }

    with _USAGE_LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(clean_record, ensure_ascii=False) + "\n")
