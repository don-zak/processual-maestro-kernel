from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from processual_api.services.supervisor_session_write_guard import (
    SupervisorSessionWriteGuardError,
    require_validated_supervisor_write_session,
    supervisor_session_header_value,
    supervisor_session_write_guard_store_path,
)
from processual_api.supervisor_session_keys import issue_supervisor_session_key


def _supervisor_session_keys_test_helper_module():
    helper_path = Path("tests/test_admin_supervisor_session_keys.py").resolve()
    spec = importlib.util.spec_from_file_location(
        "pmk_supervisor_session_keys_test_helpers",
        helper_path,
    )

    if spec is None or spec.loader is None:
        raise AssertionError("Could not load supervisor session key test helpers")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RequestStub:
    def __init__(self, headers: dict[str, str]) -> None:
        self.headers = headers


def _issuer() -> dict[str, object]:
    module = _supervisor_session_keys_test_helper_module()
    return dict(module._owner())


def _issue_session(
    store: Path,
    *,
    scopes: list[str],
) -> dict[str, object]:
    payloads = [
        {
            "label": "15B supervisor write guard test",
            "level": "operations_supervisor",
            "scopes": scopes,
            "expires_in_hours": 1,
        },
        {
            "label": "15B supervisor write guard test",
            "level": "operations_supervisor",
            "scopes": scopes,
            "ttl_hours": 1,
        },
        {
            "label": "15B supervisor write guard test",
            "level": "operations_supervisor",
            "scopes": scopes,
        },
    ]

    last_error: Exception | None = None

    for payload in payloads:
        try:
            issued = issue_supervisor_session_key(store, _issuer(), payload)

            raw_store = json.loads(store.read_text(encoding="utf-8"))
            records = raw_store.get("supervisor_session_keys") or []

            for record in records:
                if (
                    str(record.get("session_key_id") or "")
                    == str(issued["record"]["session_key_id"])
                ):
                    record["scopes"] = list(scopes)

            store.write_text(
                json.dumps(raw_store, ensure_ascii=False, sort_keys=True),
                encoding="utf-8",
            )

            issued["record"]["scopes"] = list(scopes)
            return issued
        except Exception as exc:  # pragma: no cover - version fallback
            last_error = exc

    raise AssertionError(f"Could not issue supervisor session: {last_error}")


def test_15b_guard_reads_canonical_header_before_legacy() -> None:
    request = RequestStub(
        {
            "X-Supervisor-Session-Key": "canonical-session",
            "X-Admin-Supervisor-Session": "legacy-session",
        }
    )

    assert supervisor_session_header_value(request) == "canonical-session"


def test_15b_guard_requires_supervisor_session() -> None:
    with pytest.raises(SupervisorSessionWriteGuardError) as exc_info:
        require_validated_supervisor_write_session(
            RequestStub({}),
            {"admin:integration_readiness:write"},
            guard_name="integration readiness writes",
            store_path=Path("does-not-matter.json"),
        )

    exc = exc_info.value
    assert exc.error == "supervisor_session_required"
    assert exc.session_present is False
    assert exc.session_validated is False


def test_15b_guard_rejects_fake_session_even_with_forged_scope(
    tmp_path: Path,
) -> None:
    with pytest.raises(SupervisorSessionWriteGuardError) as exc_info:
        require_validated_supervisor_write_session(
            RequestStub(
                {
                    "X-Admin-Supervisor-Session": "fake-session",
                    "X-Admin-Supervisor-Scope": (
                        "admin:integration_readiness:write"
                    ),
                }
            ),
            {"admin:integration_readiness:write"},
            guard_name="integration readiness writes",
            store_path=tmp_path / "supervisor_session_keys.json",
        )

    exc = exc_info.value
    assert exc.error == "invalid_supervisor_session"
    assert exc.session_present is True
    assert exc.session_validated is False


def test_15b_guard_ignores_forged_scope_header_without_session_scope(
    tmp_path: Path,
) -> None:
    store = tmp_path / "supervisor_session_keys.json"
    issued = _issue_session(
        store,
        scopes=["admin:integration_readiness:review"],
    )

    with pytest.raises(SupervisorSessionWriteGuardError) as exc_info:
        require_validated_supervisor_write_session(
            RequestStub(
                {
                    "X-Admin-Supervisor-Session": str(issued["raw_key"]),
                    "X-Admin-Supervisor-Scope": (
                        "admin:integration_readiness:write"
                    ),
                }
            ),
            {"admin:integration_readiness:write"},
            guard_name="integration readiness writes",
            store_path=store,
        )

    exc = exc_info.value
    assert exc.error == "supervisor_scope_required"
    assert exc.session_present is True
    assert exc.session_validated is True
    assert exc.session_key_id == issued["record"]["session_key_id"]
    assert "admin:integration_readiness:review" in exc.provided_scopes


def test_15b_guard_accepts_valid_canonical_session_scope(
    tmp_path: Path,
) -> None:
    store = tmp_path / "supervisor_session_keys.json"
    issued = _issue_session(
        store,
        scopes=["admin:integration_readiness:write"],
    )

    safe = require_validated_supervisor_write_session(
        RequestStub({"X-Supervisor-Session-Key": str(issued["raw_key"])}),
        {"admin:integration_readiness:write"},
        guard_name="integration readiness writes",
        store_path=store,
    )

    assert safe["session_present"] is True
    assert safe["session_validated"] is True
    assert safe["session_key_id"] == issued["record"]["session_key_id"]
    assert safe["provided_scopes"] == ["admin:integration_readiness:write"]
    assert "raw_key" not in safe
    assert str(issued["raw_key"]) not in str(safe)


def test_15b_guard_accepts_valid_legacy_session_header(
    tmp_path: Path,
) -> None:
    store = tmp_path / "supervisor_session_keys.json"
    issued = _issue_session(
        store,
        scopes=["admin:integration_readiness:write"],
    )

    safe = require_validated_supervisor_write_session(
        RequestStub({"X-Admin-Supervisor-Session": str(issued["raw_key"])}),
        {"admin:integration_readiness:write"},
        guard_name="integration readiness writes",
        store_path=store,
    )

    assert safe["session_key_id"] == issued["record"]["session_key_id"]


def test_15b_guard_uses_configured_store_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    store = tmp_path / "configured_supervisor_session_keys.json"
    monkeypatch.setenv("PMK_SUPERVISOR_SESSION_KEYS_PATH", str(store))

    assert supervisor_session_write_guard_store_path() == store

    issued = _issue_session(
        store,
        scopes=["admin:integration_readiness:write"],
    )

    safe = require_validated_supervisor_write_session(
        RequestStub({"X-Supervisor-Session-Key": str(issued["raw_key"])}),
        {"admin:integration_readiness:write"},
        guard_name="integration readiness writes",
    )

    assert safe["session_key_id"] == issued["record"]["session_key_id"]
