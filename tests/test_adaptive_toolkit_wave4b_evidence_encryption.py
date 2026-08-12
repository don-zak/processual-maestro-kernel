from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from processual_kernel.adaptive_toolkit import AdaptiveGovernanceToolkit
from processual_kernel.audit import AuditEventType


def make_toolkit() -> AdaptiveGovernanceToolkit:
    toolkit = object.__new__(AdaptiveGovernanceToolkit)
    toolkit.kernel = Mock()
    toolkit.efficiency_governor = Mock()
    toolkit.report_encryptor = Mock()
    toolkit.operations_governor = Mock()
    toolkit.strategy_bandit = Mock()
    toolkit.store = None
    toolkit._evidence_digests = {}
    toolkit._evidence_deltas = {}
    toolkit._encrypted_reports = {}
    toolkit._audit_adaptive = Mock()
    toolkit._persist = Mock()
    toolkit.build_adaptive_evidence_pack = Mock()
    return toolkit


def test_adaptive_evidence_digest_builds_pack_when_missing_and_records_result() -> None:
    toolkit = make_toolkit()
    pack = SimpleNamespace(workflow_id="wf-1")
    digest = SimpleNamespace(
        source_schema_version="1.8.0",
        digest_schema_version="1.0.0",
        artifact_count=4,
        stable_checksum="abc123",
    )
    toolkit.build_adaptive_evidence_pack.return_value = pack
    toolkit.efficiency_governor.evidence_pack_digest.return_value = digest

    result = toolkit.adaptive_evidence_digest("wf-1", omit_artifacts=("history",))

    assert result is digest
    toolkit.build_adaptive_evidence_pack.assert_called_once_with("wf-1")
    toolkit.efficiency_governor.evidence_pack_digest.assert_called_once_with(
        pack, omit_artifacts=("history",)
    )
    assert toolkit._evidence_digests["wf-1"] == [digest]
    toolkit._audit_adaptive.assert_called_once_with(
        AuditEventType.ADAPTIVE_EVIDENCE_DIGEST,
        "wf-1",
        {
            "workflow_id": "wf-1",
            "source_schema_version": "1.8.0",
            "digest_schema_version": "1.0.0",
            "artifact_count": 4,
            "stable_checksum": "abc123",
            "payload": digest,
        },
    )
    toolkit._persist.assert_called_once_with("adaptive_evidence_digests", digest)


def test_adaptive_evidence_digest_uses_supplied_pack_without_rebuilding() -> None:
    toolkit = make_toolkit()
    pack = SimpleNamespace(workflow_id="wf-1")
    digest = SimpleNamespace(
        source_schema_version="1.8.0",
        digest_schema_version="1.0.0",
        artifact_count=1,
        stable_checksum="supplied",
    )
    toolkit.efficiency_governor.evidence_pack_digest.return_value = digest

    result = toolkit.adaptive_evidence_digest("wf-1", pack=pack)

    assert result is digest
    toolkit.build_adaptive_evidence_pack.assert_not_called()
    toolkit.efficiency_governor.evidence_pack_digest.assert_called_once_with(
        pack, omit_artifacts=()
    )


def test_adaptive_evidence_delta_records_governor_result() -> None:
    toolkit = make_toolkit()
    previous = SimpleNamespace(stable_checksum="old")
    current = SimpleNamespace(stable_checksum="new")
    delta = SimpleNamespace(
        changed_count=2,
        unchanged_count=3,
        schema_version="1.0.0",
    )
    toolkit.efficiency_governor.evidence_delta_digest.return_value = delta

    result = toolkit.adaptive_evidence_delta("wf-1", previous, current)

    assert result is delta
    toolkit.efficiency_governor.evidence_delta_digest.assert_called_once_with(previous, current)
    assert toolkit._evidence_deltas["wf-1"] == [delta]
    toolkit._audit_adaptive.assert_called_once_with(
        AuditEventType.ADAPTIVE_EVIDENCE_DELTA,
        "wf-1",
        {
            "workflow_id": "wf-1",
            "changed_count": 2,
            "unchanged_count": 3,
            "schema_version": "1.0.0",
            "payload": delta,
        },
    )
    toolkit._persist.assert_called_once_with("adaptive_evidence_deltas", delta)


def test_encrypt_adaptive_report_records_and_optionally_writes_envelope() -> None:
    toolkit = make_toolkit()
    report = SimpleNamespace(kind="review")
    encrypted = SimpleNamespace(
        report_kind="adaptive_review",
        algorithm="AES-256-GCM",
        key_id="key-7",
        ciphertext_sha256="cipher",
        plaintext_sha256="plain",
    )
    toolkit.report_encryptor.encrypt_report.return_value = encrypted
    path = Path("encrypted-report.json")

    result = toolkit.encrypt_adaptive_report(
        "wf-1",
        report,
        "secret-key",
        report_kind="adaptive_review",
        key_id="key-7",
        path=path,
    )

    assert result is encrypted
    toolkit.report_encryptor.encrypt_report.assert_called_once_with(
        workflow_id="wf-1",
        report=report,
        key="secret-key",
        report_kind="adaptive_review",
        key_id="key-7",
    )
    assert toolkit._encrypted_reports["wf-1"] == [encrypted]
    toolkit._persist.assert_called_once_with("encrypted_reports", encrypted)
    toolkit.report_encryptor.write_encrypted_report.assert_called_once_with(encrypted, path)
    audit_payload = toolkit._audit_adaptive.call_args.args
    assert audit_payload[0] is AuditEventType.ADAPTIVE_REPORT_ENCRYPTION
    assert audit_payload[1] == "wf-1"
    assert audit_payload[2]["ciphertext_sha256"] == "cipher"
    assert audit_payload[2]["plaintext_sha256"] == "plain"
    assert "secret-key" not in repr(audit_payload[2])


def test_export_adaptive_memory_requires_path_without_store() -> None:
    toolkit = make_toolkit()

    with pytest.raises(ValueError, match="export path is required"):
        toolkit.export_adaptive_memory()

    toolkit.strategy_bandit.export_json.assert_not_called()
