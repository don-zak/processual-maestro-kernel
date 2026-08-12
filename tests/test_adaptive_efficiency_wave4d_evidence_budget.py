from __future__ import annotations

from types import SimpleNamespace

from processual_kernel.adaptive.efficiency import AdaptiveEfficiencyGovernor


def _digest(
    *,
    stable: str,
    counts: str = "counts-a",
    artifacts: dict[str, str] | None = None,
):
    return SimpleNamespace(
        workflow_id="wf-1",
        stable_checksum=stable,
        counts_checksum=counts,
        artifact_checksums={} if artifacts is None else artifacts,
    )


def test_evidence_delta_reports_unchanged_pack() -> None:
    governor = AdaptiveEfficiencyGovernor()
    previous = _digest(stable="same", artifacts={"a": "1", "b": "2"})
    current = _digest(stable="same", artifacts={"a": "1", "b": "2"})

    delta = governor.evidence_delta_digest(previous, current)

    assert delta.workflow_id == "wf-1"
    assert delta.changed_artifacts == ()
    assert delta.added_artifacts == ()
    assert delta.removed_artifacts == ()
    assert delta.unchanged_artifacts == ("a", "b")
    assert delta.changed_count == 0
    assert delta.unchanged_count == 2
    assert delta.reason == "evidence pack is unchanged"


def test_evidence_delta_distinguishes_count_only_and_artifact_changes() -> None:
    governor = AdaptiveEfficiencyGovernor()
    previous = _digest(stable="old", counts="counts-a", artifacts={"a": "1", "b": "2"})
    count_only = _digest(stable="new-count", counts="counts-b", artifacts={"a": "1", "b": "2"})
    changed = _digest(stable="new-artifacts", artifacts={"a": "9", "c": "3"})

    count_delta = governor.evidence_delta_digest(previous, count_only)
    artifact_delta = governor.evidence_delta_digest(previous, changed)

    assert count_delta.changed_count == 0
    assert count_delta.reason == "only evidence counts changed"
    assert artifact_delta.changed_artifacts == ("a",)
    assert artifact_delta.added_artifacts == ("c",)
    assert artifact_delta.removed_artifacts == ("b",)
    assert artifact_delta.unchanged_artifacts == ()
    assert artifact_delta.changed_count == 3
    assert "inspect changed" in artifact_delta.reason


def test_evidence_pack_digest_is_stable_supports_omissions_and_warns_on_missing_count_keys() -> None:
    governor = AdaptiveEfficiencyGovernor()
    pack = SimpleNamespace(
        workflow_id="wf-1",
        schema_version="1.8.0",
        artifacts={
            "profile": {"risk": "low"},
            "policy": {"name": "safe", "thresholds": {"b": 2, "a": 1}},
        },
        counts={"profile": 1, "policy": 1, "runtime_commands": 3},
    )
    equivalent = SimpleNamespace(
        workflow_id="wf-1",
        schema_version="1.8.0",
        artifacts={
            "policy": {"thresholds": {"a": 1, "b": 2}, "name": "safe"},
            "profile": {"risk": "low"},
        },
        counts={"runtime_commands": 3, "policy": 1, "profile": 1},
    )

    digest = governor.evidence_pack_digest(pack, omit_artifacts=("profile",))
    equivalent_digest = governor.evidence_pack_digest(equivalent, omit_artifacts=("profile",))

    assert digest.workflow_id == "wf-1"
    assert digest.source_schema_version == "1.8.0"
    assert digest.digest_schema_version == "adaptive-evidence-digest-1.8.0"
    assert digest.artifact_count == 1
    assert set(digest.artifact_checksums) == {"policy"}
    assert digest.omitted_artifacts == ("profile",)
    assert digest.stable_checksum == equivalent_digest.stable_checksum
    assert digest.counts_checksum == equivalent_digest.counts_checksum
    assert digest.warnings == ("some count keys are represented by singular artifacts or optional evidence",)


def test_evidence_pack_digest_ignores_expected_singular_optional_count_keys() -> None:
    governor = AdaptiveEfficiencyGovernor()
    pack = SimpleNamespace(
        workflow_id="wf-1",
        schema_version="1.8.0",
        artifacts={},
        counts={
            "operating_contracts": 1,
            "contract_validations": 2,
            "convergence_reports": 1,
            "recovery_playbooks": 1,
            "evidence_pack_validations": 1,
        },
    )

    digest = governor.evidence_pack_digest(pack)

    assert digest.artifact_count == 0
    assert digest.warnings == ()


def test_encrypted_report_index_handles_empty_duplicate_and_latest_metadata() -> None:
    governor = AdaptiveEfficiencyGovernor()

    empty = governor.encrypted_report_index("wf-1", ())
    reports = (
        SimpleNamespace(report_kind="adaptive_review", key_id="k1", ciphertext_sha256="dup", created_at=10.0),
        SimpleNamespace(report_kind="evidence_pack", key_id="k2", ciphertext_sha256="dup", created_at=25.0),
    )
    indexed = governor.encrypted_report_index("wf-1", reports)

    assert empty.encrypted_count == 0
    assert empty.latest_created_at is None
    assert empty.warnings == ("no encrypted adaptive reports are currently indexed",)
    assert indexed.encrypted_count == 2
    assert indexed.report_kinds == ("adaptive_review", "evidence_pack")
    assert indexed.key_ids == ("k1", "k2")
    assert indexed.latest_created_at == 25.0
    assert indexed.warnings == ("duplicate ciphertext hashes detected; verify report idempotency",)


def test_ui_snapshot_builds_status_deduplicates_recommendations_and_uses_encrypted_index() -> None:
    governor = AdaptiveEfficiencyGovernor()
    pack = SimpleNamespace(
        workflow_id="wf-1",
        artifacts={
            "profile": {"risk": "high"},
            "policy": {"name": "guarded", "runtime_mode": "observe"},
            "quality_gate": {"passed": True, "warnings": ["review latency"]},
            "runtime_invariants": {"passed": False, "warnings": ["review latency", "human gate required"]},
            "efficiency_reports": [{"recommendations": ["batch replay"]}],
            "convergence_report": {"recommendations": ["hold mode"]},
            "metrics": {"outcome_coverage_ratio": 0.7},
        },
        counts={"encrypted_reports": 0, "checkpoints": 3},
    )
    digest = SimpleNamespace(stable_checksum="digest-1")
    encrypted_index = SimpleNamespace(encrypted_count=2, latest_created_at=77.0)

    snapshot = governor.ui_snapshot_from_evidence_pack(
        pack,
        digest=digest,
        encrypted_index=encrypted_index,
        max_recommendations=3,
    )

    assert snapshot.workflow_id == "wf-1"
    assert snapshot.status == "quality-gate:passed | invariants:attention"
    assert snapshot.risk == "high"
    assert snapshot.policy_name == "guarded"
    assert snapshot.runtime_mode == "observe"
    assert snapshot.digest_checksum == "digest-1"
    assert snapshot.encrypted_report_count == 2
    assert snapshot.latest_encrypted_report_at == 77.0
    assert snapshot.top_recommendations == ("batch replay", "review latency", "human gate required")
    assert snapshot.warnings == ()


def test_ui_snapshot_falls_back_to_metrics_recommendation_and_warns_without_digest_or_encryption() -> None:
    governor = AdaptiveEfficiencyGovernor()
    pack = SimpleNamespace(
        workflow_id="wf-1",
        artifacts={"metrics": {"decision_quality": 0.6}},
        counts={},
    )

    snapshot = governor.ui_snapshot_from_evidence_pack(pack)

    assert snapshot.status == "review-ready"
    assert snapshot.top_recommendations == ("review metrics snapshot before changing runtime mode",)
    assert snapshot.encrypted_report_count == 0
    assert snapshot.digest_checksum is None
    assert snapshot.warnings == (
        "no encrypted reports are attached to this snapshot",
        "snapshot has no evidence digest checksum",
    )


def test_outcome_sweep_handles_empty_bounded_due_and_deferred_entries() -> None:
    governor = AdaptiveEfficiencyGovernor()

    empty = governor.plan_outcome_sweep("wf-1", 0, max_batch_size=3, min_age_seconds=10, now=100)
    entries = (
        SimpleNamespace(decision_id="oldest", created_at=10.0),
        SimpleNamespace(decision_id="middle", created_at=50.0),
        SimpleNamespace(decision_id="fresh", created_at=95.0),
    )
    bounded = governor.plan_outcome_sweep(
        "wf-1",
        3,
        max_batch_size=1,
        min_age_seconds=20,
        pending_entries=entries,
        now=100,
    )
    deferred = governor.plan_outcome_sweep(
        "wf-1",
        1,
        max_batch_size=5,
        min_age_seconds=20,
        pending_entries=(SimpleNamespace(decision_id="fresh", created_at=95.0),),
        now=100,
    )

    assert empty.batch_size == 0
    assert empty.reason == "no pending outcomes to evaluate"
    assert bounded.selected_decision_ids == ("oldest",)
    assert bounded.due_count == 2
    assert bounded.deferred_count == 1
    assert bounded.remaining_count == 2
    assert "bounded remainder" in bounded.reason
    assert deferred.selected_decision_ids == ()
    assert deferred.deferred_count == 1
    assert "younger than the minimum age" in deferred.reason


def test_outcome_sweep_without_entries_covers_unbounded_and_bounded_plans() -> None:
    governor = AdaptiveEfficiencyGovernor()

    all_items = governor.plan_outcome_sweep("wf-1", 4, max_batch_size=None)
    bounded = governor.plan_outcome_sweep("wf-1", 4, max_batch_size=2)
    fitting = governor.plan_outcome_sweep("wf-1", 2, max_batch_size=4)

    assert all_items.batch_size == 4
    assert all_items.remaining_count == 0
    assert "all pending outcomes" in all_items.reason
    assert bounded.batch_size == 2
    assert bounded.remaining_count == 2
    assert "batched" in bounded.reason
    assert fitting.batch_size == 2
    assert "fit within batch limit" in fitting.reason


def test_workload_budget_sanitizes_inputs_and_distinguishes_allowed_disabled_exhausted() -> None:
    governor = AdaptiveEfficiencyGovernor()

    allowed = governor.workload_budget_decision("wf-1", "replay", used_count=-3, limit=5, cost_units=2)
    disabled = governor.workload_budget_decision("wf-1", "export", used_count=0, limit=-1, cost_units=0)
    exhausted = governor.workload_budget_decision("wf-1", "sweep", used_count=4, limit=5, cost_units=2)

    assert allowed.allowed
    assert allowed.used_count == 0
    assert allowed.cost_units == 2
    assert allowed.remaining_after == 3
    assert "allows" in allowed.reason
    assert not disabled.allowed
    assert disabled.limit == 0
    assert disabled.cost_units == 1
    assert "disabled" in disabled.reason
    assert not exhausted.allowed
    assert exhausted.remaining_after == 1
    assert "exhausted" in exhausted.reason
