from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_authentication_does_not_consume_evaluation_quota() -> None:
    source = _read("processual_api/services/evaluation_authority_postgres.py")
    verify = source.split("async def verify_evaluation_api_key", 1)[1]
    assert "key.usage_count += 1" not in verify
    assert '"quota_semantics": "admitted_execution"' in verify


def test_new_delivery_claim_consumes_quota_transactionally() -> None:
    source = _read("processual_api/services/evaluation_runtime_delivery_postgres.py")
    assert "async def _consume_admission_quota" in source
    assert ".with_for_update()" in source
    assert "key.usage_count += 1" in source
    assert "usage_count = await _consume_admission_quota(" in source
    assert '"status": "replay"' in source
    replay_section = source.split('"status": "replay"', 1)[1]
    assert "_consume_admission_quota" not in replay_section


def test_quota_exhaustion_is_http_429() -> None:
    source = _read("processual_api/routers/evaluation_runtime.py")
    assert "EvaluationQuotaExceededError" in source
    assert "status.HTTP_429_TOO_MANY_REQUESTS" in source
    assert "Evaluation execution quota is exhausted." in source
