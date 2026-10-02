from __future__ import annotations

from pathlib import Path


def test_llm_reporter_does_not_return_or_log_raw_exception_text() -> None:
    source = Path("processual_api/cgt_governor/reports/llm_reporter.py").read_text(encoding="utf-8")

    assert "logger.exception(" not in source
    assert "str(e)" not in source
    assert "str(exc)" not in source
    assert '"exception_type": type(exc).__name__' in source
    assert '"LLM report generation failed."' in source


def test_llm_reporter_unknown_provider_error_is_generic() -> None:
    source = Path("processual_api/cgt_governor/reports/llm_reporter.py").read_text(encoding="utf-8")

    assert '"Unsupported LLM provider."' in source
    assert 'f"Unknown provider: {provider}"' not in source
