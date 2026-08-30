import asyncio
import json

import pytest
from fastapi import HTTPException

from processual_api.routers import reports
from processual_api.schemas.reports import LLMReportRequest


def test_generate_llm_report_fails_closed_when_configured_credential_cannot_decrypt(monkeypatch, tmp_path):
    settings_path = tmp_path / "settings_default.json"
    settings_path.write_text(
        json.dumps(
            {
                "llm_provider": {
                    "configured": True,
                    "provider": "generic_openai_compatible",
                    "model": "llama3",
                    "encrypted_key": "not-a-valid-envelope",
                }
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(reports, "_DATA_DIR", tmp_path)
    monkeypatch.delenv("PROCESSUAL_CRYPTO_KEY_B64", raising=False)

    async def should_not_generate(**kwargs):
        raise AssertionError("LLM generation must not run with an unavailable configured credential")

    from processual_api.cgt_governor.reports import llm_reporter

    monkeypatch.setattr(llm_reporter, "generate_llm_report", should_not_generate)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            reports.generate_llm_report(
                LLMReportRequest(fate_vector={"stability": 1.0}),
                _user="test-user",
            )
        )

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == "Configured LLM credential is unavailable"
