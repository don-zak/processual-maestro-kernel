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
    assert "async def _lock_admission_authority" in source
    assert "def _consume_admission_quota" in source
    assert ".with_for_update()" in source
    assert "key.usage_count += 1" in source

    claim = source.split("async def claim_evaluation_execution", 1)[1].split(
        "async def complete_evaluation_execution", 1
    )[0]
    quota_call = "usage_count = _consume_admission_quota(key, now=now)"
    assert quota_call in claim
    assert "# Re-read after authority locks." in claim
    before_quota = claim.split(quota_call, 1)[0]
    assert before_quota.count("if existing is not None:") >= 2
    assert before_quota.count("return _resolve_existing_claim(") >= 2
    assert '"status": "claimed"' in claim


def test_quota_rejection_commits_before_http_429_translation() -> None:
    source = _read("processual_api/services/evaluation_runtime_delivery_postgres.py")
    assert "_record_quota_rejection(key)" in source
    assert "quota_exhausted = True" in source
    assert "# Raise only after the session context has committed rejection telemetry." in source
    assert 'raise EvaluationQuotaExceededError("evaluation_execution_quota_exhausted")' in source


def test_quota_exhaustion_is_http_429() -> None:
    source = _read("processual_api/routers/evaluation_runtime.py")
    assert "EvaluationQuotaExceededError" in source
    assert "status.HTTP_429_TOO_MANY_REQUESTS" in source
    assert "Evaluation execution quota is exhausted." in source
