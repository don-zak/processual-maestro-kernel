"""Persistent Stage 18 enterprise qualification grant store.

The store contains safe qualification records and audit metadata only.
It never stores raw API keys, raw supervisor session keys, provider secrets,
authorization headers, or production/runtime approvals.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

STORE_VERSION = 1


def qualification_store_path() -> Path:
    configured = os.environ.get(
        "PMK_ENTERPRISE_QUALIFICATION_STORE_PATH",
        "",
    ).strip()

    if configured:
        return Path(configured)

    return (
        Path(__file__).resolve().parents[1]
        / "data"
        / "enterprise_qualification_grants_18.json"
    )


def empty_qualification_store() -> dict[str, Any]:
    return {
        "version": STORE_VERSION,
        "grants": [],
        "decisions": [],
        "audit": [],
    }


def load_qualification_store(
    path: Path | None = None,
) -> dict[str, Any]:
    target = path or qualification_store_path()

    if not target.exists():
        return empty_qualification_store()

    try:
        raw = json.loads(
            target.read_text(encoding="utf-8")
        )
    except (
        json.JSONDecodeError,
        OSError,
        UnicodeError,
    ) as exc:
        raise ValueError(
            "Enterprise qualification store is unreadable."
        ) from exc

    if not isinstance(raw, dict):
        raise ValueError(
            "Enterprise qualification store must be an object."
        )

    if raw.get("version") != STORE_VERSION:
        raise ValueError(
            "Unsupported enterprise qualification store version."
        )

    for key in ("grants", "decisions", "audit"):
        if not isinstance(raw.get(key), list):
            raise ValueError(
                f"Enterprise qualification store field {key} must be a list."
            )

    return raw


def save_qualification_store(
    data: dict[str, Any],
    path: Path | None = None,
) -> None:
    target = path or qualification_store_path()
    target.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "version": STORE_VERSION,
        "grants": list(data.get("grants") or []),
        "decisions": list(data.get("decisions") or []),
        "audit": list(data.get("audit") or []),
    }

    forbidden_keys = {
        "api_key",
        "raw_key",
        "hashed",
        "hash",
        "provider_secret",
        "authorization",
        "supervisor_session_key",
    }

    def validate_safe(value: Any) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if str(key).lower() in forbidden_keys:
                    raise ValueError(
                        "Raw credential material is forbidden "
                        "in the enterprise qualification store."
                    )
                validate_safe(child)
            return

        if isinstance(value, list):
            for child in value:
                validate_safe(child)

    validate_safe(payload)

    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) + "\n"

    temporary_path: Path | None = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=target.parent,
            prefix=f".{target.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            handle.write(serialized)
            handle.flush()
            os.fsync(handle.fileno())
            temporary_path = Path(handle.name)

        os.replace(temporary_path, target)

    except OSError:
        if temporary_path is not None:
            temporary_path.unlink(
                missing_ok=True
            )
        raise


def append_qualification_audit(
    store: dict[str, Any],
    *,
    event: str,
    case_id: str,
    client_id: str,
    supervisor_id: str,
    supervisor_session_key_id: str,
    grant_id: str = "",
    task_ids: tuple[str, ...] = (),
    occurred_at: str,
    reason: str = "",
) -> dict[str, Any]:
    entry = {
        "event": event,
        "case_id": case_id,
        "client_id": client_id,
        "supervisor_id": supervisor_id,
        "supervisor_session_key_id": (
            supervisor_session_key_id
        ),
        "grant_id": grant_id,
        "task_ids": list(task_ids),
        "occurred_at": occurred_at,
        "reason": reason,
        "production_allowed": False,
        "runtime_connector_approved": False,
        "raw_secret_visible": False,
    }

    store.setdefault("audit", []).append(entry)

    return entry
