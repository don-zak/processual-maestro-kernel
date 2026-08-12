from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from types import SimpleNamespace

from processual_kernel.adaptive.history import WorkflowHistoryRecorder
from processual_kernel.adaptive.ledger import DecisionLedger
from processual_kernel.adaptive.persistence import AdaptiveJsonStore, _json_default
from processual_kernel.adaptive.policy_profiles import build_policy_profiles
from processual_kernel.adaptive_types import (
    CheckpointKind,
    CheckpointReport,
    DecisionOutcome,
    PolicyName,
    StrategySuggestion,
    WorkflowHistoryEvent,
)
from processual_kernel.types import AgentState, MaestroAction


def _outcome(decision_id: str, action: str = "retry", *, quality: float = 0.4) -> DecisionOutcome:
    return DecisionOutcome(
        decision_id=decision_id,
        action=action,
        expected_effect="improve",
        actual_result="success",
        quality_delta=0.2,
        cost_delta=-0.1,
        latency_delta=-0.2,
        recovery_time_delta=-0.3,
        success_probability_delta=0.25,
        human_feedback_score=0.8,
        decision_quality=quality,
        created_at=123.0,
    )


def _checkpoint(*, confidence: float = 0.8, risks: tuple[str, ...] = (), action=MaestroAction.OBSERVE):
    return CheckpointReport(
        workflow_id="wf-1",
        kind=CheckpointKind.EVENT_BASED,
        checkpoint_number=3,
        policy_name=PolicyName.BALANCED,
        policy_version="balanced-1.0.0",
        workflow_status={"state": "running"},
        agent_findings={"agents": 2},
        handoff_findings={"edges": 1},
        risks=risks,
        recommended_action=action,
        confidence=confidence,
        created_at=111.0,
    )


def test_history_record_checkpoint_builds_base_and_risk_events():
    recorder = WorkflowHistoryRecorder()
    report = _checkpoint(
        risks=("weak_handoffs:a->b", "failed_steps:s1", "other:risk"),
        action=MaestroAction.REROUTE,
    )

    events = recorder.record_checkpoint(report)

    assert [event.event_type for event in events] == [
        "checkpoint",
        "handoff_degradation",
        "repeated_failure",
    ]
    checkpoint, handoff, failure = events
    assert checkpoint.action == MaestroAction.REROUTE
    assert checkpoint.quality_delta == 0.02
    assert checkpoint.latency_delta == -0.01
    assert checkpoint.metadata == {
        "checkpoint_number": 3,
        "checkpoint_kind": "event_based",
        "confidence": 0.8,
        "risks": ["weak_handoffs:a->b", "failed_steps:s1", "other:risk"],
    }
    assert handoff.action == MaestroAction.REROUTE
    assert handoff.quality_delta == 0.03
    assert handoff.metadata["risk"] == "weak_handoffs:a->b"
    assert failure.action == MaestroAction.RETRY
    assert failure.cost_delta == 0.03
    assert failure.latency_delta == 0.03
    assert recorder.history("wf-1") == events


def test_history_record_checkpoint_low_confidence_and_non_latency_action():
    recorder = WorkflowHistoryRecorder()

    (event,) = recorder.record_checkpoint(_checkpoint(confidence=0.5, action=MaestroAction.OBSERVE))

    assert event.quality_delta == -0.01
    assert event.latency_delta == 0.0


def test_history_record_outcome_maps_known_action_and_policy():
    recorder = WorkflowHistoryRecorder()
    policy = build_policy_profiles()[PolicyName.BALANCED]
    outcome = _outcome("d-1", "retry", quality=0.72)

    event = recorder.record_outcome("wf-1", outcome, policy)

    assert event.event_type == "decision_outcome"
    assert event.action == MaestroAction.RETRY
    assert event.policy_name == PolicyName.BALANCED
    assert event.quality_delta == 0.2
    assert event.cost_delta == -0.1
    assert event.latency_delta == -0.2
    assert event.success_probability_delta == 0.25
    assert event.metadata == {
        "decision_id": "d-1",
        "actual_result": "success",
        "decision_quality": 0.72,
    }
    assert event.created_at == 123.0


def test_history_record_outcome_unknown_action_and_no_policy():
    recorder = WorkflowHistoryRecorder()

    event = recorder.record_outcome("wf-2", _outcome("d-2", "custom-action"))

    assert event.action is None
    assert event.policy_name is None


def test_history_record_cycle_prefers_budget_action_then_strategy():
    recorder = WorkflowHistoryRecorder()
    policy = build_policy_profiles()[PolicyName.BALANCED]
    strategy = StrategySuggestion(
        strategy=MaestroAction.PAUSE,
        confidence=0.6,
        sample_size=10,
        reason="history",
        safe_to_apply=False,
    )
    report = SimpleNamespace(
        workflow_id="wf-3",
        budget_action=MaestroAction.ARCHIVE,
        strategy_suggestion=strategy,
        policy=policy,
        checkpoint=_checkpoint(),
        drift_alerts=(1, 2),
        handoff_suggestions=(1,),
        policy_patches=(1, 2, 3),
        outcome_coverage_ratio=0.75,
        decision_id="cycle-d",
        created_at=456.0,
    )

    event = recorder.record_cycle(report)

    assert event.action == MaestroAction.ARCHIVE
    assert event.policy_name == PolicyName.BALANCED
    assert event.quality_delta == 0.01
    assert event.created_at == 456.0
    assert event.metadata == {
        "decision_id": "cycle-d",
        "checkpoint_created": True,
        "drift_alert_count": 2,
        "handoff_suggestion_count": 1,
        "patch_count": 3,
        "outcome_coverage_ratio": 0.75,
    }

    report.budget_action = None
    report.checkpoint = None
    second = recorder.record_cycle(report)
    assert second.action == MaestroAction.PAUSE
    assert second.quality_delta == 0.0
    assert second.metadata["checkpoint_created"] is False


def test_history_extend_history_and_clear_scopes():
    recorder = WorkflowHistoryRecorder()
    first = WorkflowHistoryEvent(workflow_id="wf-a", event_type="a")
    second = WorkflowHistoryEvent(workflow_id="wf-a", event_type="b")
    third = WorkflowHistoryEvent(workflow_id="wf-b", event_type="c")

    recorder.extend("wf-a", (first, second))
    recorder.record(third)

    assert recorder.history("wf-a") == (first, second)
    assert recorder.history("missing") == ()
    recorder.clear("wf-a")
    assert recorder.history("wf-a") == ()
    assert recorder.history("wf-b") == (third,)
    recorder.clear()
    assert recorder.history("wf-b") == ()


def test_ledger_records_actions_state_fallback_and_metadata():
    ledger = DecisionLedger()
    action_decision = SimpleNamespace(
        decision_id="d-action",
        action=MaestroAction.REROUTE,
        workflow_id="wf-original",
        policy_version="p1",
    )
    state_decision = SimpleNamespace(
        decision_id="d-state",
        action=None,
        new_state=AgentState.ARCHIVED,
    )
    unknown_decision = SimpleNamespace(decision_id="d-unknown")

    action_entry = ledger.record(action_decision, workflow_id="wf-override", important=True, source="test")
    state_entry = ledger.record(state_decision, important=False)
    unknown_entry = ledger.record(unknown_decision)

    assert action_entry.workflow_id == "wf-override"
    assert action_entry.action == "reroute"
    assert action_entry.policy_version == "p1"
    assert action_entry.metadata == {"source": "test"}
    assert state_entry.action == "archived"
    assert state_entry.policy_version == "unversioned"
    assert state_entry.important is False
    assert unknown_entry.action == "unknown"


def test_ledger_attach_pending_and_coverage_ratio(monkeypatch):
    ledger = DecisionLedger()
    ledger.record(SimpleNamespace(decision_id="important", action=MaestroAction.RETRY), important=True)
    ledger.record(SimpleNamespace(decision_id="optional", action=MaestroAction.OBSERVE), important=False)

    assert [entry.decision_id for entry in ledger.pending()] == ["important"]
    assert {entry.decision_id for entry in ledger.pending(important_only=False)} == {"important", "optional"}
    assert ledger.coverage_ratio() == 0.0
    assert ledger.coverage_ratio(important_only=False) == 0.0
    assert ledger.attach_outcome(_outcome("missing")) is None

    monkeypatch.setattr("processual_kernel.adaptive.ledger.time.time", lambda: 999.0)
    attached = ledger.attach_outcome(_outcome("important"))
    assert attached is ledger.entries["important"]
    assert attached.outcome is not None
    assert attached.outcome_recorded_at == 999.0
    assert ledger.pending() == ()
    assert ledger.coverage_ratio() == 1.0
    assert ledger.coverage_ratio(important_only=False) == 0.5


def test_ledger_empty_coverage_is_complete():
    assert DecisionLedger().coverage_ratio() == 1.0


class ExampleEnum(Enum):
    VALUE = "value"


@dataclass
class ExampleData:
    name: str
    state: ExampleEnum


class ValueObject:
    value = "custom-value"


class PlainObject:
    def __str__(self):
        return "plain-object"


def test_json_default_handles_dataclass_enum_value_and_fallback():
    assert _json_default(ExampleData("x", ExampleEnum.VALUE)) == {"name": "x", "state": ExampleEnum.VALUE}
    assert _json_default(ExampleEnum.VALUE) == "value"
    assert _json_default(ValueObject()) == "custom-value"
    assert _json_default(PlainObject()) == "plain-object"


def test_json_store_append_append_many_and_list_records(tmp_path):
    store = AdaptiveJsonStore(tmp_path / "nested" / "evidence")
    assert store.root.exists()
    assert store.list_records("events") == ()

    first_path = store.append("events", WorkflowHistoryEvent(workflow_id="wf", event_type="one"))
    second_path = store.append_many(
        "events",
        (
            {"workflow_id": "wf", "event_type": "two"},
            {"workflow_id": "wf", "event_type": "three", "action": MaestroAction.RETRY},
        ),
    )

    assert first_path == second_path == store.root / "events.jsonl"
    records = store.list_records("events")
    assert [record["event_type"] for record in records] == ["one", "two", "three"]
    assert records[2]["action"] == "retry"

    with first_path.open("a", encoding="utf-8") as handle:
        handle.write("\n   \n")
    assert len(store.list_records("events")) == 3


def test_json_store_snapshot_round_trip_and_missing(tmp_path):
    store = AdaptiveJsonStore(tmp_path)
    assert store.load_snapshot("missing") == {}

    snapshot_path = store.save_snapshot(
        "state",
        {
            "mode": ExampleEnum.VALUE,
            "data": ExampleData("item", ExampleEnum.VALUE),
            "action": MaestroAction.PAUSE,
        },
    )

    assert snapshot_path == tmp_path / "state.json"
    loaded = store.load_snapshot("state")
    assert loaded == {
        "mode": "value",
        "data": {"name": "item", "state": "value"},
        "action": "pause",
    }
    raw = json.loads(snapshot_path.read_text(encoding="utf-8"))
    assert raw == loaded
