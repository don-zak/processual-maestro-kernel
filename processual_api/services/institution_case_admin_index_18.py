"""Safe cross-user index for Stage 18 institution integration cases.

The service scans only settings_<user_id>.json files and returns restricted
administrative projections. It never trusts owner_user_id from an HTTP request
and never exposes task references, notes, manifests, credentials, or secrets.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class InstitutionCaseAdminIndexError(ValueError):
    """Safe institution-case index failure."""


def settings_owner_user_id(path: Path) -> str:
    stem = str(path.stem)

    if not stem.startswith("settings_"):
        raise InstitutionCaseAdminIndexError(
            "institution_settings_filename_invalid"
        )

    owner_user_id = stem.removeprefix("settings_").strip()

    if not owner_user_id:
        raise InstitutionCaseAdminIndexError(
            "institution_settings_owner_missing"
        )

    return owner_user_id


def institution_settings_files(
    data_dir: Path,
) -> list[Path]:
    data_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    return sorted(
        path
        for path in data_dir.glob("settings_*.json")
        if path.is_file()
    )


def load_settings_document(
    path: Path,
) -> dict[str, Any]:
    try:
        payload = json.loads(
            path.read_text(encoding="utf-8")
        )
    except (
        json.JSONDecodeError,
        OSError,
        UnicodeError,
    ) as exc:
        raise InstitutionCaseAdminIndexError(
            "institution_settings_document_unreadable"
        ) from exc

    if not isinstance(payload, dict):
        raise InstitutionCaseAdminIndexError(
            "institution_settings_document_invalid"
        )

    return payload


def institution_case_progress(
    case: dict[str, Any],
) -> int:
    tasks = case.get("tasks")

    if not isinstance(tasks, list) or not tasks:
        return 0

    completed = sum(
        1
        for task in tasks
        if isinstance(task, dict)
        and task.get("status") == "completed"
    )

    return round(
        completed * 100 / len(tasks)
    )


def safe_institution_case_summary(
    case: dict[str, Any],
    *,
    owner_user_id: str,
) -> dict[str, Any]:
    case_id = str(
        case.get("case_id") or ""
    ).strip()
    client_id = str(
        case.get("client_id") or ""
    ).strip()

    if not case_id or not client_id:
        raise InstitutionCaseAdminIndexError(
            "institution_case_identity_invalid"
        )

    tasks = case.get("tasks")
    task_count = (
        len(tasks)
        if isinstance(tasks, list)
        else 0
    )

    validation_counts = {
        "passed": 0,
        "pending": 0,
        "blocked": 0,
        "not_checked": 0,
    }

    if isinstance(tasks, list):
        for task in tasks:
            if not isinstance(task, dict):
                continue

            state = str(
                task.get("validation")
                or "not_checked"
            )

            if state not in validation_counts:
                state = "not_checked"

            validation_counts[state] += 1

    return {
        "case_id": case_id,
        "client_id": client_id,
        "owner_user_id": owner_user_id,
        "case_type": str(
            case.get("case_type") or ""
        ),
        "integration_track": str(
            case.get("integration_track") or ""
        ),
        "title": str(
            case.get("title") or ""
        )[:160],
        "status": str(
            case.get("status") or "draft"
        ),
        "phase": str(
            case.get("phase")
            or "technical_intake"
        ),
        "task_count": task_count,
        "progress_percent": (
            institution_case_progress(case)
        ),
        "validation_counts": (
            validation_counts
        ),
        "created_at": case.get(
            "created_at"
        ),
        "updated_at": case.get(
            "updated_at"
        ),
        "sandbox_requested": bool(
            case.get(
                "sandbox_requested",
                True,
            )
        ),
        "production_allowed": False,
        "runtime_connector_approved": False,
        "external_http_allowed": False,
        "raw_secret_visible": False,
    }


def list_safe_institution_cases(
    *,
    data_dir: Path,
    status: str | None = None,
    phase: str | None = None,
    client_id: str | None = None,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []

    for path in institution_settings_files(
        data_dir
    ):
        try:
            owner_user_id = (
                settings_owner_user_id(path)
            )
            raw = load_settings_document(
                path
            )
        except InstitutionCaseAdminIndexError:
            continue

        cases = raw.get(
            "institution_integration_cases"
        )

        if not isinstance(cases, list):
            continue

        for case in cases:
            if not isinstance(case, dict):
                continue

            try:
                summary = (
                    safe_institution_case_summary(
                        case,
                        owner_user_id=(
                            owner_user_id
                        ),
                    )
                )
            except InstitutionCaseAdminIndexError:
                continue

            if (
                status is not None
                and summary["status"] != status
            ):
                continue

            if (
                phase is not None
                and summary["phase"] != phase
            ):
                continue

            if (
                client_id is not None
                and summary["client_id"]
                != client_id
            ):
                continue

            results.append(summary)

    results.sort(
        key=lambda item: str(
            item.get("updated_at")
            or item.get("created_at")
            or ""
        ),
        reverse=True,
    )

    return results


def qualification_review_queue(
    *,
    data_dir: Path,
) -> dict[str, Any]:
    cases = list_safe_institution_cases(
        data_dir=data_dir,
        status="ready_for_review",
        phase="supervisor_decision",
    )

    return {
        "status": "ready",
        "queue_count": len(cases),
        "cases": cases,
        "production_allowed": False,
        "runtime_connector_approved": False,
        "external_http_allowed": False,
        "raw_secret_visible": False,
    }


def resolve_institution_case(
    *,
    data_dir: Path,
    case_id: str,
) -> tuple[str, dict[str, Any]]:
    requested = str(case_id or "").strip()

    if not requested:
        raise InstitutionCaseAdminIndexError(
            "institution_case_not_found"
        )

    matches: list[
        tuple[str, dict[str, Any]]
    ] = []

    for path in institution_settings_files(
        data_dir
    ):
        try:
            owner_user_id = (
                settings_owner_user_id(path)
            )
            raw = load_settings_document(
                path
            )
        except InstitutionCaseAdminIndexError:
            continue

        cases = raw.get(
            "institution_integration_cases"
        )

        if not isinstance(cases, list):
            continue

        for case in cases:
            if (
                isinstance(case, dict)
                and str(
                    case.get("case_id") or ""
                )
                == requested
            ):
                matches.append(
                    (
                        owner_user_id,
                        case,
                    )
                )

    if not matches:
        raise InstitutionCaseAdminIndexError(
            "institution_case_not_found"
        )

    if len(matches) > 1:
        raise InstitutionCaseAdminIndexError(
            "institution_case_identity_conflict"
        )

    return matches[0]
