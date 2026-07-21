import json
from pathlib import Path

import pytest

from processual_api.services.enterprise_qualification_decisions_18 import (
    QualificationDecisionError,
    approve_sandbox_qualification,
    list_safe_qualification_grants,
    qualification_review_summary,
    request_qualification_revision,
)
from processual_api.services.enterprise_qualification_store_18 import (
    empty_qualification_store,
    load_qualification_store,
    save_qualification_store,
)


def _case(
    *,
    status: str = "ready_for_review",
    phase: str = "supervisor_decision",
    client_id: str = "client_demo",
) -> dict:
    return {
        "case_id": "icase_demo",
        "client_id": client_id,
        "integration_track": "camara",
        "status": status,
        "phase": phase,
        "tasks": [
            {
                "task_id": "capability_profile",
                "validation": "passed",
            },
            {
                "task_id": "consent_reference",
                "validation": "passed",
            },
            {
                "task_id": "sandbox_endpoint",
                "validation": "passed",
            },
            {
                "task_id": "conformance_evidence",
                "validation": "passed",
            },
        ],
    }


def test_empty_store_is_safe_and_versioned(
    tmp_path: Path,
) -> None:
    path = tmp_path / "qualification.json"

    result = load_qualification_store(path)

    assert result == empty_qualification_store()
    assert result["version"] == 1
    assert result["grants"] == []
    assert result["decisions"] == []
    assert result["audit"] == []


def test_store_rejects_raw_credential_material(
    tmp_path: Path,
) -> None:
    path = tmp_path / "qualification.json"
    store = empty_qualification_store()

    store["grants"].append(
        {
            "grant_id": "qgrant_demo",
            "raw_key": "forbidden",
        }
    )

    with pytest.raises(
        ValueError,
        match="Raw credential material",
    ):
        save_qualification_store(
            store,
            path,
        )

    assert not path.exists()


def test_review_summary_requires_validated_case() -> None:
    valid = qualification_review_summary(
        _case()
    )

    assert valid["reviewable"] is True
    assert valid["blockers"] == []
    assert valid["executable_task_ids"] == [
        "sandbox_capability_probe"
    ]
    assert valid["production_allowed"] is False
    assert (
        valid["runtime_connector_approved"]
        is False
    )

    invalid = qualification_review_summary(
        _case(status="in_progress")
    )

    assert invalid["reviewable"] is False
    assert (
        "case_not_ready_for_review"
        in invalid["blockers"]
    )


def test_approval_requires_supervisor_session(
    tmp_path: Path,
) -> None:
    with pytest.raises(
        QualificationDecisionError,
        match="Validated supervisor session",
    ):
        approve_sandbox_qualification(
            case=_case(),
            supervisor_id="supervisor_demo",
            supervisor_session_key_id="",
            approved_task_ids=(
                "sandbox_capability_probe",
            ),
            store_path=(
                tmp_path / "qualification.json"
            ),
        )


def test_approval_rejects_reference_task(
    tmp_path: Path,
) -> None:
    with pytest.raises(
        QualificationDecisionError,
        match="registered executable tasks",
    ):
        approve_sandbox_qualification(
            case=_case(),
            supervisor_id="supervisor_demo",
            supervisor_session_key_id=(
                "supsk_demo"
            ),
            approved_task_ids=(
                "consent_reference",
            ),
            store_path=(
                tmp_path / "qualification.json"
            ),
        )


def test_approval_creates_safe_grant_decision_and_audit(
    tmp_path: Path,
) -> None:
    path = tmp_path / "qualification.json"

    result = approve_sandbox_qualification(
        case=_case(),
        supervisor_id="supervisor_demo",
        supervisor_session_key_id=(
            "supsk_demo"
        ),
        approved_task_ids=(
            "sandbox_capability_probe",
        ),
        reason="Validated sandbox readiness.",
        ttl_days=7,
        store_path=path,
    )

    assert result["status"] == "approved"
    assert result["grant"]["case_id"] == (
        "icase_demo"
    )
    assert result["grant"]["client_id"] == (
        "client_demo"
    )
    assert result["grant"]["status"] == (
        "approved"
    )
    assert result["grant"]["environment"] == (
        "sandbox"
    )

    assert (
        "supervisor_session_key_id"
        not in result["grant"]
    )

    assert (
        result["grant"]["production_allowed"]
        is False
    )
    assert (
        result["grant"][
            "runtime_connector_approved"
        ]
        is False
    )
    assert (
        result["grant"]["raw_secret_visible"]
        is False
    )

    persisted = json.loads(
        path.read_text(encoding="utf-8")
    )

    assert len(persisted["grants"]) == 1
    assert len(persisted["decisions"]) == 1
    assert len(persisted["audit"]) == 1

    assert (
        persisted["audit"][0]["event"]
        == "qualification_approved"
    )

    serialized = path.read_text(
        encoding="utf-8"
    ).lower()

    assert '"api_key"' not in serialized
    assert '"raw_key"' not in serialized
    assert '"provider_secret"' not in serialized


def test_duplicate_active_grant_is_rejected(
    tmp_path: Path,
) -> None:
    path = tmp_path / "qualification.json"

    approve_sandbox_qualification(
        case=_case(),
        supervisor_id="supervisor_demo",
        supervisor_session_key_id=(
            "supsk_demo"
        ),
        approved_task_ids=(
            "sandbox_capability_probe",
        ),
        store_path=path,
    )

    with pytest.raises(
        QualificationDecisionError,
        match="active qualification grant",
    ):
        approve_sandbox_qualification(
            case=_case(),
            supervisor_id="supervisor_demo",
            supervisor_session_key_id=(
                "supsk_demo"
            ),
            approved_task_ids=(
                "sandbox_capability_probe",
            ),
            store_path=path,
        )


def test_revision_decision_requires_reason(
    tmp_path: Path,
) -> None:
    with pytest.raises(
        QualificationDecisionError,
        match="Revision reason",
    ):
        request_qualification_revision(
            case=_case(),
            supervisor_id="supervisor_demo",
            supervisor_session_key_id=(
                "supsk_demo"
            ),
            reason="",
            store_path=(
                tmp_path / "qualification.json"
            ),
        )


def test_revision_decision_is_persisted_without_grant(
    tmp_path: Path,
) -> None:
    path = tmp_path / "qualification.json"

    result = request_qualification_revision(
        case=_case(),
        supervisor_id="supervisor_demo",
        supervisor_session_key_id=(
            "supsk_demo"
        ),
        reason="Correct the endpoint reference.",
        store_path=path,
    )

    assert result["status"] == (
        "revision_required"
    )

    store = load_qualification_store(path)

    assert store["grants"] == []
    assert len(store["decisions"]) == 1
    assert len(store["audit"]) == 1
    assert (
        store["audit"][0]["event"]
        == "qualification_revision_requested"
    )


def test_client_safe_grant_listing_is_isolated(
    tmp_path: Path,
) -> None:
    path = tmp_path / "qualification.json"

    approve_sandbox_qualification(
        case=_case(),
        supervisor_id="supervisor_demo",
        supervisor_session_key_id=(
            "supsk_demo"
        ),
        approved_task_ids=(
            "sandbox_capability_probe",
        ),
        store_path=path,
    )

    matching = list_safe_qualification_grants(
        client_id="client_demo",
        case_id="icase_demo",
        store_path=path,
    )

    other_client = (
        list_safe_qualification_grants(
            client_id="client_other",
            store_path=path,
        )
    )

    assert len(matching) == 1
    assert other_client == []

    grant = matching[0]

    assert (
        "supervisor_session_key_id"
        not in grant
    )
    assert grant["production_allowed"] is False
    assert (
        grant["runtime_connector_approved"]
        is False
    )
    assert grant["raw_secret_visible"] is False
