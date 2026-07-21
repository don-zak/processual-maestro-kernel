import json
from pathlib import Path

import pytest

from processual_api.services.institution_case_admin_index_18 import (
    InstitutionCaseAdminIndexError,
    institution_settings_files,
    list_safe_institution_cases,
    qualification_review_queue,
    resolve_institution_case,
    settings_owner_user_id,
)


def _case(
    *,
    case_id: str = "icase_demo",
    client_id: str = "client_demo",
    status: str = "ready_for_review",
    phase: str = "supervisor_decision",
) -> dict:
    return {
        "case_id": case_id,
        "client_id": client_id,
        "case_type": (
            "camara_integration_case"
        ),
        "integration_track": "camara",
        "title": "CAMARA qualification",
        "status": status,
        "phase": phase,
        "tasks": [
            {
                "task_id": (
                    "capability_profile"
                ),
                "status": "completed",
                "validation": "passed",
                "reference": (
                    "internal-sensitive-ref"
                ),
                "note": (
                    "must not be exposed"
                ),
            },
            {
                "task_id": (
                    "consent_reference"
                ),
                "status": "completed",
                "validation": "passed",
                "reference": (
                    "another-sensitive-ref"
                ),
            },
        ],
        "created_at": (
            "2026-07-20T10:00:00+00:00"
        ),
        "updated_at": (
            "2026-07-20T11:00:00+00:00"
        ),
        "sandbox_requested": True,
        "production_allowed": False,
        "runtime_connector_approved": False,
    }


def _write_settings(
    path: Path,
    cases: list[dict],
) -> None:
    path.write_text(
        json.dumps(
            {
                "institution_integration_cases": (
                    cases
                )
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def test_only_settings_prefixed_files_are_scanned(
    tmp_path: Path,
) -> None:
    _write_settings(
        tmp_path / "settings_user_a.json",
        [_case()],
    )
    _write_settings(
        tmp_path / "other.json",
        [_case(case_id="wrong")],
    )

    files = institution_settings_files(
        tmp_path
    )

    assert files == [
        tmp_path / "settings_user_a.json"
    ]


def test_owner_user_id_comes_from_filename() -> None:
    assert (
        settings_owner_user_id(
            Path("settings_user_a.json")
        )
        == "user_a"
    )

    with pytest.raises(
        InstitutionCaseAdminIndexError,
        match=(
            "institution_settings_filename_invalid"
        ),
    ):
        settings_owner_user_id(
            Path("other.json")
        )


def test_safe_queue_excludes_references_and_notes(
    tmp_path: Path,
) -> None:
    _write_settings(
        tmp_path / "settings_user_a.json",
        [_case()],
    )

    queue = qualification_review_queue(
        data_dir=tmp_path
    )

    assert queue["queue_count"] == 1
    assert len(queue["cases"]) == 1

    summary = queue["cases"][0]

    assert summary["case_id"] == (
        "icase_demo"
    )
    assert summary["client_id"] == (
        "client_demo"
    )
    assert summary["owner_user_id"] == (
        "user_a"
    )
    assert summary["progress_percent"] == 100
    assert summary["task_count"] == 2

    serialized = repr(queue).lower()

    assert "internal-sensitive-ref" not in serialized
    assert "another-sensitive-ref" not in serialized
    assert "must not be exposed" not in serialized
    assert '"reference"' not in serialized
    assert '"note"' not in serialized

    assert queue["production_allowed"] is False
    assert (
        queue["runtime_connector_approved"]
        is False
    )
    assert queue["raw_secret_visible"] is False


def test_queue_only_contains_review_ready_cases(
    tmp_path: Path,
) -> None:
    _write_settings(
        tmp_path / "settings_user_a.json",
        [
            _case(),
            _case(
                case_id="icase_draft",
                status="in_progress",
                phase="technical_intake",
            ),
        ],
    )

    queue = qualification_review_queue(
        data_dir=tmp_path
    )

    assert [
        case["case_id"]
        for case in queue["cases"]
    ] == ["icase_demo"]


def test_cross_user_listing_is_safe(
    tmp_path: Path,
) -> None:
    _write_settings(
        tmp_path / "settings_user_a.json",
        [
            _case(
                case_id="icase_a",
                client_id="client_a",
            )
        ],
    )
    _write_settings(
        tmp_path / "settings_user_b.json",
        [
            _case(
                case_id="icase_b",
                client_id="client_b",
            )
        ],
    )

    results = list_safe_institution_cases(
        data_dir=tmp_path
    )

    assert {
        item["owner_user_id"]
        for item in results
    } == {"user_a", "user_b"}

    client_a = (
        list_safe_institution_cases(
            data_dir=tmp_path,
            client_id="client_a",
        )
    )

    assert len(client_a) == 1
    assert (
        client_a[0]["case_id"]
        == "icase_a"
    )


def test_case_resolution_derives_owner_internally(
    tmp_path: Path,
) -> None:
    _write_settings(
        tmp_path / "settings_owner_real.json",
        [_case()],
    )

    owner, case = resolve_institution_case(
        data_dir=tmp_path,
        case_id="icase_demo",
    )

    assert owner == "owner_real"
    assert case["client_id"] == (
        "client_demo"
    )


def test_unknown_case_is_not_found(
    tmp_path: Path,
) -> None:
    with pytest.raises(
        InstitutionCaseAdminIndexError,
        match="institution_case_not_found",
    ):
        resolve_institution_case(
            data_dir=tmp_path,
            case_id="missing",
        )


def test_duplicate_case_ids_fail_closed(
    tmp_path: Path,
) -> None:
    _write_settings(
        tmp_path / "settings_user_a.json",
        [_case()],
    )
    _write_settings(
        tmp_path / "settings_user_b.json",
        [_case()],
    )

    with pytest.raises(
        InstitutionCaseAdminIndexError,
        match=(
            "institution_case_identity_conflict"
        ),
    ):
        resolve_institution_case(
            data_dir=tmp_path,
            case_id="icase_demo",
        )


def test_corrupt_settings_file_does_not_break_queue(
    tmp_path: Path,
) -> None:
    (
        tmp_path
        / "settings_corrupt.json"
    ).write_text(
        "{invalid",
        encoding="utf-8",
    )

    _write_settings(
        tmp_path / "settings_valid.json",
        [_case()],
    )

    queue = qualification_review_queue(
        data_dir=tmp_path
    )

    assert queue["queue_count"] == 1
