import asyncio
import base64
import json

import pytest
from fastapi import HTTPException

import processual_api.cgt_governor.reports as reports_module
import processual_api.routers.cgt_governor as cgt_router


class _FakeStore:
    def __init__(self, entries=None):
        self.entries = list(entries or [])

    def __len__(self):
        return len(self.entries)


def _entry(eval_id, rank, reward, ts):
    return {
        "eval_id": eval_id,
        "rank": rank,
        "reward": reward,
        "policy": "accept" if rank == "stable" else "repair_scaffold",
        "policy_label": "Accept" if rank == "stable" else "Repair",
        "fate_vector": {"stability": reward},
        "ts": ts,
    }


def test_governor_reports_filters_and_summarizes_entries(monkeypatch):
    entries = [
        _entry("eval_1", "stable", 0.8, "2026-06-01T10:00:00+00:00"),
        _entry("eval_2", "extinct", 0.2, "2026-06-02T10:00:00+00:00"),
        _entry("eval_3", "stable", 1.0, "2026-06-03T10:00:00+00:00"),
    ]

    monkeypatch.setattr(cgt_router, "eval_store", _FakeStore(entries))
    monkeypatch.setattr(cgt_router, "decrypt_log_entry", lambda entry, key: entry)

    result = asyncio.run(
        cgt_router.governor_reports(
            rank="stable",
            date_from="2026-06-01",
            date_to="2026-06-30",
            page=1,
            page_size=10,
            current_user={"sub": "test-user"},
        )
    )

    assert result["total"] == 2
    assert result["rank_distribution"] == {"stable": 2}
    assert result["avg_reward"] == 0.9

    report_rows = (
        result.get("entries")
        or result.get("items")
        or result.get("results")
        or result.get("evaluations")
        or []
    )
    if report_rows:
        assert [row["eval_id"] for row in report_rows] == ["eval_1", "eval_3"]


def test_export_reports_json_filters_and_sets_download_headers(monkeypatch):
    entries = [
        _entry("eval_1", "stable", 0.8, "2026-06-01T10:00:00+00:00"),
        _entry("eval_2", "extinct", 0.2, "2026-06-02T10:00:00+00:00"),
        _entry("eval_3", "stable", 1.0, "2026-06-03T10:00:00+00:00"),
    ]

    monkeypatch.setattr(cgt_router, "eval_store", _FakeStore(entries))
    monkeypatch.setattr(cgt_router, "decrypt_log_entry", lambda entry, key: entry)

    response = asyncio.run(
        cgt_router.export_reports_json(
            rank="stable",
            date_from=None,
            date_to=None,
            current_user={"sub": "test-user"},
        )
    )

    assert response.media_type == "application/json"
    assert "reports.json" in response.headers["content-disposition"]

    payload = json.loads(response.body.decode("utf-8"))
    assert [entry["eval_id"] for entry in payload] == ["eval_1", "eval_3"]


def test_governor_reports_pdf_returns_signed_pdf_response(monkeypatch):
    entries = [
        _entry("eval_1", "stable", 0.8, "2026-06-01T10:00:00+00:00"),
        _entry("eval_2", "extinct", 0.2, "2026-06-02T10:00:00+00:00"),
    ]
    pdf_calls = []

    def fake_generate_governance_pdf(entry, language="en", signature=""):
        pdf_calls.append(
            {
                "entry": entry,
                "language": language,
                "signature": signature,
            }
        )
        return b"%PDF-test-summary"

    monkeypatch.setattr(cgt_router, "eval_store", _FakeStore(entries))
    monkeypatch.setattr(cgt_router, "decrypt_log_entry", lambda entry, key: entry)
    monkeypatch.setattr(cgt_router, "sign_response", lambda payload: "sig-summary")
    monkeypatch.setattr(
        reports_module,
        "generate_governance_pdf",
        fake_generate_governance_pdf,
    )

    response = asyncio.run(
        cgt_router.governor_reports_pdf(
            lang="en",
            current_user={"sub": "test-user"},
        )
    )

    assert response.media_type == "application/pdf"
    assert response.body == b"%PDF-test-summary"
    assert response.headers["x-signature"] == "sig-summary"
    assert "governance-report-en.pdf" in response.headers["content-disposition"]

    assert pdf_calls[0]["language"] == "en"
    assert pdf_calls[0]["signature"] == "sig-summary"
    assert pdf_calls[0]["entry"]["rank"] == "Summary - 2 evaluations"
    assert pdf_calls[0]["entry"]["reward"] == 0.5


def test_governor_eval_pdf_returns_specific_signed_pdf_or_404(monkeypatch):
    entries = [
        _entry("eval_1", "stable", 0.8, "2026-06-01T10:00:00+00:00"),
        _entry("eval_target", "hybrid", 0.4, "2026-06-02T10:00:00+00:00"),
    ]
    pdf_calls = []

    def fake_generate_governance_pdf(entry, language="en", signature=""):
        pdf_calls.append(
            {
                "entry": entry,
                "language": language,
                "signature": signature,
            }
        )
        return b"%PDF-test-eval"

    monkeypatch.setattr(cgt_router, "eval_store", _FakeStore(entries))
    monkeypatch.setattr(cgt_router, "decrypt_log_entry", lambda entry, key: entry)
    monkeypatch.setattr(
        cgt_router,
        "sign_response",
        lambda payload: f"sig-{payload['eval_id']}",
    )
    monkeypatch.setattr(
        reports_module,
        "generate_governance_pdf",
        fake_generate_governance_pdf,
    )

    response = asyncio.run(
        cgt_router.governor_eval_pdf(
            eval_id="eval_target",
            lang="ar",
            current_user={"sub": "test-user"},
        )
    )

    assert response.media_type == "application/pdf"
    assert response.body == b"%PDF-test-eval"
    assert response.headers["x-signature"] == "sig-eval_target"
    assert "governance-eval-eval_target-ar.pdf" in response.headers[
        "content-disposition"
    ]

    assert pdf_calls[0]["entry"]["eval_id"] == "eval_target"
    assert pdf_calls[0]["language"] == "ar"
    assert pdf_calls[0]["signature"] == "sig-eval_target"

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            cgt_router.governor_eval_pdf(
                eval_id="missing_eval",
                lang="en",
                current_user={"sub": "test-user"},
            )
        )

    assert exc_info.value.status_code == 404


def test_govern_report_returns_json_payload_with_base64_pdf(monkeypatch):
    pdf_bytes = b"%PDF-single-report"
    pdf_calls = []

    def fake_generate_governance_pdf(entry, language="en", signature=""):
        pdf_calls.append(
            {
                "entry": entry,
                "language": language,
                "signature": signature,
            }
        )
        return pdf_bytes

    def fake_evaluate_and_record(
        answer,
        language,
        scores,
        context=None,
        reason="govern",
    ):
        assert answer == "Report this governed answer."
        assert language == "en"
        assert scores == {"compatibility": 0.88}
        assert reason == "report"

        response_data = {
            "rank": "stable",
            "reward": 0.88,
            "policy": "accept",
            "policy_label": "Accept",
            "fate_vector": {"stability": 0.88},
        }
        entry = {
            **response_data,
            "ts": "2026-06-01T10:00:00+00:00",
            "eval_id": "eval_report_1",
        }
        return {
            "response_data": response_data,
            "signature": "sig-report",
            "governance_action": "keep",
            "action_label": "Keep - Accept Response",
            "entry": entry,
        }

    monkeypatch.setattr(cgt_router, "_resolve_scores", lambda req: {"compatibility": 0.88})
    monkeypatch.setattr(cgt_router, "_evaluate_and_record", fake_evaluate_and_record)
    monkeypatch.setattr(
        reports_module,
        "generate_governance_pdf",
        fake_generate_governance_pdf,
    )

    result = asyncio.run(
        cgt_router.govern_report(
            cgt_router.ReportRequest(
                answer="Report this governed answer.",
                language="en",
            ),
            current_user={"sub": "test-user"},
        )
    )

    assert result["rank"] == "stable"
    assert result["reward"] == 0.88
    assert result["signature"] == "sig-report"
    assert result["governance_action"] == "keep"
    assert result["eval_id"] == "eval_report_1"
    assert result["pdf_base64"] == base64.b64encode(pdf_bytes).decode("ascii")

    assert pdf_calls[0]["entry"]["eval_id"] == "eval_report_1"
    assert pdf_calls[0]["language"] == "en"
    assert pdf_calls[0]["signature"] == "sig-report"
