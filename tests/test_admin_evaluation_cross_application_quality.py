from __future__ import annotations

from processual_api.services import evaluation_cross_application_quality as cross_quality


def test_cross_application_quality_requires_at_least_two_distinct_campaigns() -> None:
    result = cross_quality.assess_cross_application_quality(
        {},
        client_ids=("external-app-a",),
    )

    assert result["cross_application_quality_sufficient"] is False
    assert result["observed_application_count"] == 1
    assert result["blocker_codes"] == [
        "multiple_external_application_campaigns_required"
    ]


def test_each_external_application_must_pass_endpoint_and_semantic_quality(monkeypatch) -> None:
    def endpoint_quality(*, client_id: str, **_kwargs):
        return {
            "quality_gate_passed": client_id != "external-app-b",
            "quality_evidence_percent": 100.0 if client_id != "external-app-b" else 83.33,
        }

    def task_quality(_raw, *, client_id: str, **_kwargs):
        return {
            "semantic_quality_sufficient": True,
            "task_binding_count": 2,
        }

    monkeypatch.setattr(cross_quality, "assess_evaluation_campaign_quality", endpoint_quality)
    monkeypatch.setattr(cross_quality, "summarize_evaluation_task_quality", task_quality)

    result = cross_quality.assess_cross_application_quality(
        {},
        client_ids=("external-app-a", "external-app-b"),
    )

    assert result["cross_application_quality_sufficient"] is False
    assert result["passed_application_count"] == 1
    app_b = next(item for item in result["applications"] if item["client_id"] == "external-app-b")
    assert app_b["endpoint_quality_passed"] is False
    assert "endpoint_quality_incomplete" in app_b["blocker_codes"]


def test_cross_application_quality_passes_only_when_every_application_passes(monkeypatch) -> None:
    monkeypatch.setattr(
        cross_quality,
        "assess_evaluation_campaign_quality",
        lambda **kwargs: {
            "quality_gate_passed": True,
            "quality_evidence_percent": 100.0,
        },
    )
    monkeypatch.setattr(
        cross_quality,
        "summarize_evaluation_task_quality",
        lambda raw, **kwargs: {
            "semantic_quality_sufficient": True,
            "task_binding_count": 3,
        },
    )

    result = cross_quality.assess_cross_application_quality(
        {},
        client_ids=("external-app-a", "external-app-b"),
    )

    assert result["observed_application_count"] == 2
    assert result["passed_application_count"] == 2
    assert result["cross_application_quality_sufficient"] is True
    assert result["blocker_codes"] == []
    assert result["public_probe_evidence_required_per_application"] is True


def test_semantic_failure_in_one_application_blocks_portability(monkeypatch) -> None:
    monkeypatch.setattr(
        cross_quality,
        "assess_evaluation_campaign_quality",
        lambda **kwargs: {
            "quality_gate_passed": True,
            "quality_evidence_percent": 100.0,
        },
    )

    def task_quality(_raw, *, client_id: str, **_kwargs):
        return {
            "semantic_quality_sufficient": client_id != "external-app-b",
            "task_binding_count": 3,
        }

    monkeypatch.setattr(cross_quality, "summarize_evaluation_task_quality", task_quality)

    result = cross_quality.assess_cross_application_quality(
        {},
        client_ids=("external-app-a", "external-app-b"),
    )

    assert result["cross_application_quality_sufficient"] is False
    app_b = next(item for item in result["applications"] if item["client_id"] == "external-app-b")
    assert app_b["semantic_task_quality_passed"] is False
    assert "semantic_task_quality_incomplete" in app_b["blocker_codes"]
