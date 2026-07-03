from __future__ import annotations

import json

import processual_api.services.usage_log_store as usage_log_store


def _write_usage_log(path, records):
    path.write_text(
        "\n".join(json.dumps(record, ensure_ascii=False) for record in records)
        + "\n",
        encoding="utf-8",
    )


def test_summarize_usage_logs_returns_empty_summary_for_missing_ledger(
    tmp_path,
    monkeypatch,
):
    usage_log_path = tmp_path / "usage_logs.jsonl"
    monkeypatch.setattr(usage_log_store, "_USAGE_LOG_PATH", usage_log_path)

    summary = usage_log_store.summarize_usage_logs(client_id="client-a")

    assert summary["client_id"] == "client-a"
    assert summary["total_events"] == 0
    assert summary["total_units"] == 0
    assert summary["successful_requests"] == 0
    assert summary["rejected_requests"] == 0
    assert summary["latest_events"] == []


def test_summarize_usage_logs_filters_by_client_and_counts_units(
    tmp_path,
    monkeypatch,
):
    usage_log_path = tmp_path / "usage_logs.jsonl"
    monkeypatch.setattr(usage_log_store, "_USAGE_LOG_PATH", usage_log_path)

    _write_usage_log(
        usage_log_path,
        [
            {
                "created_at": "2026-07-03T10:00:00+00:00",
                "client_id": "client-a",
                "api_key_id": "key-a",
                "method": "POST",
                "endpoint": "/cgt/govern",
                "status_code": 200,
                "latency_ms": 2.0,
                "endpoint_class": "governance_evaluation",
                "units_charged": 1,
                "quota_limit": 100,
                "quota_before": 0,
                "quota_requested": 1,
                "quota_after": 1,
                "quota_remaining": 99,
                "quota_rejected": False,
                "plan_id": "business",
            },
            {
                "created_at": "2026-07-03T10:01:00+00:00",
                "client_id": "client-a",
                "api_key_id": "key-a",
                "method": "POST",
                "endpoint": "/cgt/govern/auto-repair",
                "status_code": 429,
                "latency_ms": 4.0,
                "endpoint_class": "governance_evaluation",
                "units_charged": 5,
                "quota_limit": 100,
                "quota_before": 95,
                "quota_requested": 5,
                "quota_after": 98,
                "quota_remaining": 2,
                "quota_rejected": True,
                "plan_id": "business",
            },
            {
                "created_at": "2026-07-03T10:02:00+00:00",
                "client_id": "client-b",
                "api_key_id": "key-b",
                "method": "POST",
                "endpoint": "/reports/fate",
                "status_code": 200,
                "latency_ms": 10.0,
                "endpoint_class": "report_generation",
                "units_charged": 2,
                "quota_rejected": False,
                "plan_id": "starter",
            },
        ],
    )

    summary = usage_log_store.summarize_usage_logs(client_id="client-a")

    assert summary["client_id"] == "client-a"
    assert summary["total_events"] == 2
    assert summary["successful_requests"] == 1
    assert summary["rejected_requests"] == 1
    assert summary["total_units"] == 6
    assert summary["successful_units"] == 1
    assert summary["rejected_units"] == 5
    assert summary["quota_limit"] == 100
    assert summary["quota_used"] == 98
    assert summary["quota_remaining"] == 2
    assert summary["plan_id"] == "business"
    assert summary["by_endpoint_class"] == {"governance_evaluation": 2}
    assert summary["by_status_code"] == {"200": 1, "429": 1}
    assert summary["top_endpoints"] == {
        "/cgt/govern": 1,
        "/cgt/govern/auto-repair": 1,
    }
    assert summary["avg_latency_ms"] == 3.0


def test_summarize_usage_logs_filters_by_api_key_and_limits_latest_events(
    tmp_path,
    monkeypatch,
):
    usage_log_path = tmp_path / "usage_logs.jsonl"
    monkeypatch.setattr(usage_log_store, "_USAGE_LOG_PATH", usage_log_path)

    records = []
    for index in range(5):
        records.append({
            "created_at": f"2026-07-03T10:0{index}:00+00:00",
            "client_id": "client-a",
            "api_key_id": "key-a" if index < 4 else "key-other",
            "endpoint": "/cgt/govern",
            "status_code": 200,
            "endpoint_class": "governance_evaluation",
            "units_charged": 1,
            "quota_after": index + 1,
            "quota_remaining": 100 - index - 1,
            "quota_rejected": False,
            "plan_id": "business",
        })

    _write_usage_log(usage_log_path, records)

    summary = usage_log_store.summarize_usage_logs(
        client_id="client-a",
        api_key_id="key-a",
        latest_limit=2,
    )

    assert summary["api_key_id"] == "key-a"
    assert summary["total_events"] == 4
    assert summary["total_units"] == 4
    assert len(summary["latest_events"]) == 2
    assert summary["latest_events"][0]["created_at"] == "2026-07-03T10:03:00+00:00"
    assert summary["latest_events"][1]["created_at"] == "2026-07-03T10:02:00+00:00"


def test_summarize_usage_logs_skips_malformed_json_lines(tmp_path, monkeypatch):
    usage_log_path = tmp_path / "usage_logs.jsonl"
    monkeypatch.setattr(usage_log_store, "_USAGE_LOG_PATH", usage_log_path)

    usage_log_path.write_text(
        "{not-json}\n"
        + json.dumps({
            "client_id": "client-a",
            "api_key_id": "key-a",
            "endpoint": "/cgt/govern",
            "status_code": 200,
            "endpoint_class": "governance_evaluation",
            "units_charged": 1,
            "quota_rejected": False,
        })
        + "\n",
        encoding="utf-8",
    )

    summary = usage_log_store.summarize_usage_logs(client_id="client-a")

    assert summary["total_events"] == 1
    assert summary["total_units"] == 1
