from __future__ import annotations

from dataclasses import replace
import json

import pytest

from processual_kernel.adaptive.encryption import (
    AES_256_GCM,
    KEY_LENGTH_BYTES,
    AdaptiveReportEncryptor,
    canonical_json,
    sha256_hex_bytes,
)
from processual_kernel.adaptive.policy_profiles import get_policy_profile
from processual_kernel.adaptive.runtime_adapter import AdaptiveRuntimeAdapter
from processual_kernel.adaptive.safety import AdaptiveSafetyGuard
from processual_kernel.adaptive_types import (
    AgentCountBand,
    AmbiguityLevel,
    PolicyName,
    PolicyPatch,
    RiskLevel,
    RuntimeMode,
    TaskDuration,
    TaskProfile,
    TaskSize,
)
from processual_kernel.types import MaestroAction


def _profile(*, risk: RiskLevel = RiskLevel.LOW) -> TaskProfile:
    return TaskProfile(
        size=TaskSize.SMALL,
        duration=TaskDuration.SHORT,
        risk=risk,
        ambiguity=AmbiguityLevel.LOW,
        agent_count=AgentCountBand.SINGLE,
    )


def _patch(*, sample_size: int = 100) -> PolicyPatch:
    return PolicyPatch(
        field="max_step_attempts",
        old_value=2,
        new_value=1,
        reason="reduce repeated retries",
        policy_version_from="v1",
        policy_version_to="v2",
        sample_size=sample_size,
        runtime_mode=RuntimeMode.RECOMMEND,
    )


def test_encryption_helpers_are_deterministic_and_validate_keys():
    encryptor = AdaptiveReportEncryptor()
    raw_key = bytes(range(KEY_LENGTH_BYTES))
    encoded_key = encryptor.generate_key_b64()

    assert len(encryptor.normalize_key(raw_key)) == KEY_LENGTH_BYTES
    assert len(encryptor.normalize_key(encoded_key)) == KEY_LENGTH_BYTES
    assert canonical_json({"z": 1, "a": RiskLevel.HIGH}) == '{"a":"high","z":1}'
    assert sha256_hex_bytes(b"abc") == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"

    with pytest.raises(ValueError, match="exactly 32 key bytes"):
        encryptor.normalize_key(b"short")
    with pytest.raises(ValueError, match="invalid base64-encoded AES key"):
        encryptor.normalize_key("!!!not-base64!!!")


def test_encrypt_decrypt_round_trip_and_persist(tmp_path):
    encryptor = AdaptiveReportEncryptor()
    key = bytes(range(KEY_LENGTH_BYTES))
    report = {"schema_version": "2.0", "status": "ok", "items": [1, 2]}

    encrypted = encryptor.encrypt_report(
        "wf-encrypted",
        report,
        key,
        report_kind="adaptive-review",
        key_id="key-7",
    )
    result = encryptor.decrypt_report(encrypted, key)

    assert encrypted.algorithm == AES_256_GCM
    assert encrypted.plaintext_schema_version == "2.0"
    assert encrypted.key_id == "key-7"
    assert result.valid
    assert result.artifact == report
    assert result.reason == "decryption succeeded"
    assert result.plaintext_sha256 == encrypted.plaintext_sha256
    assert result.ciphertext_sha256 == encrypted.ciphertext_sha256

    target = encryptor.write_encrypted_report(encrypted, tmp_path / "nested" / "report.json")
    persisted = json.loads(target.read_text(encoding="utf-8"))
    assert persisted["workflow_id"] == "wf-encrypted"
    assert persisted["ciphertext_b64"] == encrypted.ciphertext_b64


def test_decryption_rejects_metadata_authentication_and_checksum_tampering():
    encryptor = AdaptiveReportEncryptor()
    key = bytes(range(KEY_LENGTH_BYTES))
    encrypted = encryptor.encrypt_report("wf", {"value": 7}, key, report_kind="review")

    unsupported = encryptor.decrypt_report(replace(encrypted, algorithm="legacy"), key)
    assert not unsupported.valid
    assert unsupported.reason == "unsupported encryption algorithm: legacy"

    aad_mismatch = encryptor.decrypt_report(replace(encrypted, key_id="other-key"), key)
    assert not aad_mismatch.valid
    assert aad_mismatch.reason == "associated data does not match encrypted report metadata"

    authentication_failure = encryptor.decrypt_report(encrypted, bytes(reversed(range(KEY_LENGTH_BYTES))))
    assert not authentication_failure.valid
    assert authentication_failure.reason == "AES-GCM authentication failed"
    assert authentication_failure.ciphertext_sha256 == encrypted.ciphertext_sha256

    checksum_failure = encryptor.decrypt_report(replace(encrypted, plaintext_sha256="0" * 64), key)
    assert not checksum_failure.valid
    assert checksum_failure.artifact is None
    assert checksum_failure.reason == "plaintext checksum mismatch"


def test_safety_guard_tracks_requests_and_pending_scope():
    guard = AdaptiveSafetyGuard()
    enum_request = guard.request_approval(
        "wf-a",
        MaestroAction.REROUTE,
        "risk detected",
        "policy-1",
        source="checkpoint",
    )
    string_request = guard.request_approval("wf-b", "custom-action", "manual", "policy-2")

    assert enum_request.action == "reroute"
    assert enum_request.metadata == {"source": "checkpoint"}
    assert string_request.action == "custom-action"
    assert guard.pending("wf-a") == (enum_request,)
    assert set(request.request_id for request in guard.pending()) == {
        enum_request.request_id,
        string_request.request_id,
    }

    approved = guard.approve(enum_request.request_id)
    assert approved.approved
    assert approved.decided_at is not None
    assert guard.pending("wf-a") == ()
    assert guard.pending() == (string_request,)


@pytest.mark.parametrize("risk", [RiskLevel.HIGH, RiskLevel.CRITICAL])
def test_safety_guard_requires_human_gate_for_high_risk(risk):
    guard = AdaptiveSafetyGuard()
    policy = get_policy_profile(PolicyName.BALANCED)
    assert guard.requires_human_gate(_profile(risk=risk), policy)


def test_safety_guard_human_gate_policy_action_and_safe_path():
    guard = AdaptiveSafetyGuard()
    safe_profile = _profile()

    assert guard.requires_human_gate(safe_profile, get_policy_profile(PolicyName.CRITICAL_SAFETY))
    assert guard.requires_human_gate(safe_profile, get_policy_profile(PolicyName.CONSERVATIVE))
    assert guard.requires_human_gate(
        safe_profile,
        get_policy_profile(PolicyName.BALANCED),
        MaestroAction.ARCHIVE,
    )
    assert not guard.requires_human_gate(safe_profile, get_policy_profile(PolicyName.BALANCED))


@pytest.mark.parametrize(
    ("toolkit_mode", "policy_name", "risk", "sample_size", "expected"),
    [
        (RuntimeMode.RECOMMEND, PolicyName.BALANCED, RiskLevel.LOW, 100, False),
        (RuntimeMode.CONTROLLED_ADAPTIVE, PolicyName.FAST, RiskLevel.LOW, 100, False),
        (RuntimeMode.CONTROLLED_ADAPTIVE, PolicyName.CRITICAL_SAFETY, RiskLevel.LOW, 100, False),
        (RuntimeMode.CONTROLLED_ADAPTIVE, PolicyName.BALANCED, RiskLevel.HIGH, 100, False),
        (RuntimeMode.CONTROLLED_ADAPTIVE, PolicyName.BALANCED, RiskLevel.LOW, 0, False),
        (RuntimeMode.CONTROLLED_ADAPTIVE, PolicyName.BALANCED, RiskLevel.LOW, 100, True),
    ],
)
def test_safety_guard_auto_patch_matrix(toolkit_mode, policy_name, risk, sample_size, expected):
    guard = AdaptiveSafetyGuard()
    allowed = guard.can_auto_apply_patch(
        _profile(risk=risk),
        get_policy_profile(policy_name),
        _patch(sample_size=sample_size),
        toolkit_mode,
    )
    assert allowed is expected


def test_runtime_adapter_builds_and_reauthorizes_immutable_commands():
    adapter = AdaptiveRuntimeAdapter()
    command = adapter.build_command(
        "wf-runtime",
        MaestroAction.PAUSE,
        payload={"source": "adaptive"},
        request_id="request-1",
    )

    assert command.subject == "wf-runtime"
    assert command.reason == "adaptive runtime command"
    assert command.payload == {"source": "adaptive"}
    assert command.dry_run
    assert not command.authorized

    authorized = adapter.with_authorization(command, authorized=True, request_id="request-2")
    assert authorized.authorized
    assert authorized.request_id == "request-2"
    assert not authorized.requires_human_approval
    assert command.request_id == "request-1"
    assert not command.authorized


@pytest.mark.parametrize(
    ("command", "reason", "requires_approval"),
    [
        (
            {"authorized": True, "requires_human_approval": True, "dry_run": False},
            "blocked pending human approval",
            True,
        ),
        (
            {"authorized": False, "requires_human_approval": False, "dry_run": False},
            "blocked because command is not authorized",
            False,
        ),
        (
            {"authorized": True, "requires_human_approval": False, "dry_run": True},
            "dry run only; no runtime mutation performed",
            False,
        ),
    ],
)
def test_runtime_adapter_blocks_before_host_mutation(command, reason, requires_approval):
    adapter = AdaptiveRuntimeAdapter()
    runtime_command = adapter.build_command(
        "wf-blocked",
        MaestroAction.PAUSE,
        payload={"x": 1},
        **command,
    )

    class Kernel:
        def intervene(self, *args):
            raise AssertionError("intervene must not be called")

    result = adapter.execute(Kernel(), runtime_command)
    assert not result.executed
    assert result.reason == reason
    assert result.requires_human_approval is requires_approval
    assert result.event_payload == {"x": 1}


def test_runtime_adapter_handles_read_only_and_host_owned_actions():
    adapter = AdaptiveRuntimeAdapter()

    class Kernel:
        def intervene(self, *args):
            raise AssertionError("intervene must not be called")

    observe = adapter.build_command("wf", MaestroAction.OBSERVE, authorized=True, dry_run=False)
    observe_result = adapter.execute(Kernel(), observe)
    assert not observe_result.executed
    assert observe_result.reason == "observe action is read-only"

    archive = adapter.build_command("wf", MaestroAction.ARCHIVE, authorized=True, dry_run=False)
    archive_result = adapter.execute(Kernel(), archive)
    assert not archive_result.executed
    assert archive_result.reason == "runtime adapter does not execute action archive; host runtime must handle it"


@pytest.mark.parametrize(
    "action",
    [MaestroAction.PAUSE, MaestroAction.REROUTE, MaestroAction.ESCALATE, MaestroAction.FINALIZE],
)
def test_runtime_adapter_executes_authorized_state_actions(action):
    adapter = AdaptiveRuntimeAdapter()
    calls = []

    class Kernel:
        def intervene(self, workflow_id, runtime_action, subject, reason, payload):
            calls.append((workflow_id, runtime_action, subject, reason, payload))
            return {"accepted": True, "action": runtime_action.value}

    command = adapter.build_command(
        "wf-live",
        action,
        subject="step-7",
        reason="approved adaptive action",
        payload={"priority": 3},
        authorized=True,
        dry_run=False,
    )
    result = adapter.execute(Kernel(), command)

    assert result.executed
    assert not result.dry_run
    assert result.authorized
    assert result.reason == "executed through kernel runtime boundary"
    assert result.event_payload == {"event": {"accepted": True, "action": action.value}}
    assert calls == [
        ("wf-live", action, "step-7", "approved adaptive action", {"priority": 3}),
    ]
