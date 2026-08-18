"""Controlled acquisition of immutable external API descriptions.

The caller never supplies a URL. A server-owned catalog binds a source identity
to one GitHub repository, contract family, approved revisions, and path prefixes.
Runtime input is limited to an immutable commit and a repository-relative path
accepted by that catalog entry. The fetch target is constructed by this module
and remains non-production evidence only.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any

import httpx
import yaml

from processual_api.integrations.endpoint_discovery_quality import (
    canonical_api_description_sha256,
)
from processual_api.integrations.endpoint_source_attestation import (
    TrustedEndpointSourceRecord,
)
from processual_api.integrations.enterprise_sandbox_execution import (
    resolve_public_addresses,
)

MAX_TRUSTED_SOURCE_BYTES = 2 * 1024 * 1024
_RAW_GITHUB_HOST = "raw.githubusercontent.com"
_GITHUB_NAME = re.compile(r"^[A-Za-z0-9_.-]{1,100}$")
_GIT_COMMIT = re.compile(r"^[0-9a-f]{40,64}$")
_SOURCE_ID = re.compile(r"^[a-z0-9][a-z0-9_.-]{2,127}$")
_SAFE_REPOSITORY_PATH = re.compile(r"^[A-Za-z0-9._/-]+$")
_SUPPORTED_FAMILIES = frozenset(
    {"camara", "tm_forum", "proprietary", "legacy", "generic_enterprise"}
)


class TrustedEndpointSourceAcquisitionError(ValueError):
    """A trusted-source request could not be safely acquired or validated."""


@dataclass(frozen=True, slots=True)
class TrustedGitHubSourceDefinition:
    source_identity_id: str
    repository: str
    contract_family: str
    allowed_path_prefixes: tuple[str, ...]
    allowed_revisions: tuple[str, ...]
    policy_version: str = "github-allowlist-r2"


@dataclass(frozen=True, slots=True)
class AcquiredTrustedEndpointSource:
    api_description: dict[str, Any]
    trusted_record: TrustedEndpointSourceRecord
    repository: str
    path: str
    fetch_host: str = _RAW_GITHUB_HOST
    production_allowed: bool = False
    runtime_connector_approved: bool = False


def _normalized_family(value: str) -> str:
    family = str(value or "").strip().lower().replace("-", "_")
    if family not in _SUPPORTED_FAMILIES:
        raise TrustedEndpointSourceAcquisitionError("trusted_source_contract_family_invalid")
    return family


def _safe_repository(value: str) -> str:
    parts = str(value or "").strip().split("/")
    if len(parts) != 2 or not all(_GITHUB_NAME.fullmatch(part) for part in parts):
        raise TrustedEndpointSourceAcquisitionError("trusted_source_repository_invalid")
    return f"{parts[0]}/{parts[1]}"


def _normalized_repository_path(value: str, *, error_code: str) -> str:
    raw = str(value or "").strip()
    if (
        not raw
        or raw.startswith("/")
        or "\\" in raw
        or len(raw) > 500
        or not _SAFE_REPOSITORY_PATH.fullmatch(raw)
    ):
        raise TrustedEndpointSourceAcquisitionError(error_code)
    path = PurePosixPath(raw)
    if any(part in {"", ".", ".."} for part in path.parts):
        raise TrustedEndpointSourceAcquisitionError(error_code)
    normalized = path.as_posix()
    if normalized != raw:
        raise TrustedEndpointSourceAcquisitionError(error_code)
    return normalized


def _safe_path(value: str) -> str:
    normalized = _normalized_repository_path(
        value,
        error_code="trusted_source_path_invalid",
    )
    if not normalized.lower().endswith((".json", ".yaml", ".yml")):
        raise TrustedEndpointSourceAcquisitionError("trusted_source_format_not_allowed")
    return normalized


def _safe_prefix(value: str) -> str:
    return _normalized_repository_path(
        str(value or "").rstrip("/"),
        error_code="trusted_source_path_prefix_invalid",
    )


def _safe_revision(value: str, *, error_code: str) -> str:
    revision = str(value or "").strip().lower()
    if not _GIT_COMMIT.fullmatch(revision):
        raise TrustedEndpointSourceAcquisitionError(error_code)
    return revision


def _definition_from_mapping(value: dict[str, Any]) -> TrustedGitHubSourceDefinition:
    source_identity_id = str(value.get("source_identity_id") or "").strip().lower()
    if not _SOURCE_ID.fullmatch(source_identity_id):
        raise TrustedEndpointSourceAcquisitionError("trusted_source_identity_invalid")
    repository = _safe_repository(str(value.get("repository") or ""))
    family = _normalized_family(str(value.get("contract_family") or ""))
    prefixes_raw = value.get("allowed_path_prefixes")
    if not isinstance(prefixes_raw, list) or not prefixes_raw:
        raise TrustedEndpointSourceAcquisitionError("trusted_source_path_prefixes_required")
    prefixes = tuple(_safe_prefix(str(item)) for item in prefixes_raw)
    revisions_raw = value.get("allowed_revisions")
    if not isinstance(revisions_raw, list) or not revisions_raw:
        raise TrustedEndpointSourceAcquisitionError("trusted_source_revisions_required")
    revisions = tuple(
        _safe_revision(str(item), error_code="trusted_source_revision_invalid")
        for item in revisions_raw
    )
    if len(revisions) != len(set(revisions)):
        raise TrustedEndpointSourceAcquisitionError("trusted_source_duplicate_revision")
    policy_version = str(value.get("policy_version") or "github-allowlist-r2").strip()
    if not policy_version or len(policy_version) > 80:
        raise TrustedEndpointSourceAcquisitionError("trusted_source_policy_version_invalid")
    return TrustedGitHubSourceDefinition(
        source_identity_id=source_identity_id,
        repository=repository,
        contract_family=family,
        allowed_path_prefixes=prefixes,
        allowed_revisions=revisions,
        policy_version=policy_version,
    )


def trusted_github_source_catalog_from_env() -> tuple[TrustedGitHubSourceDefinition, ...]:
    raw = os.environ.get("PMK_TRUSTED_GITHUB_ENDPOINT_SOURCES", "").strip()
    if not raw:
        return ()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise TrustedEndpointSourceAcquisitionError("trusted_source_catalog_invalid_json") from exc
    if not isinstance(parsed, list):
        raise TrustedEndpointSourceAcquisitionError("trusted_source_catalog_must_be_list")
    definitions = tuple(_definition_from_mapping(item) for item in parsed if isinstance(item, dict))
    if len(definitions) != len(parsed):
        raise TrustedEndpointSourceAcquisitionError("trusted_source_catalog_entry_invalid")
    ids = [item.source_identity_id for item in definitions]
    if len(ids) != len(set(ids)):
        raise TrustedEndpointSourceAcquisitionError("trusted_source_catalog_duplicate_identity")
    return definitions


def _select_definition(
    source_identity_id: str,
    catalog: tuple[TrustedGitHubSourceDefinition, ...],
) -> TrustedGitHubSourceDefinition:
    requested = str(source_identity_id or "").strip().lower()
    matches = [item for item in catalog if item.source_identity_id == requested]
    if len(matches) != 1:
        raise TrustedEndpointSourceAcquisitionError("trusted_source_identity_not_allowlisted")
    return matches[0]


def _path_allowed(path: str, prefixes: tuple[str, ...]) -> bool:
    return any(path == prefix or path.startswith(prefix + "/") for prefix in prefixes)


def _parse_api_description(content: bytes, path: str) -> dict[str, Any]:
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise TrustedEndpointSourceAcquisitionError("trusted_source_not_utf8") from exc
    try:
        if path.lower().endswith(".json"):
            parsed = json.loads(text)
        else:
            parsed = yaml.safe_load(text)
    except (json.JSONDecodeError, yaml.YAMLError) as exc:
        raise TrustedEndpointSourceAcquisitionError("trusted_source_parse_failed") from exc
    if not isinstance(parsed, dict):
        raise TrustedEndpointSourceAcquisitionError("trusted_source_document_must_be_object")
    return parsed


async def _read_bounded_response(response: httpx.Response) -> bytes:
    content = bytearray()
    async for chunk in response.aiter_bytes():
        if not chunk:
            continue
        if len(content) + len(chunk) > MAX_TRUSTED_SOURCE_BYTES:
            raise TrustedEndpointSourceAcquisitionError("trusted_source_size_invalid")
        content.extend(chunk)
    if not content:
        raise TrustedEndpointSourceAcquisitionError("trusted_source_size_invalid")
    return bytes(content)


async def acquire_trusted_github_endpoint_source(
    *,
    source_identity_id: str,
    source_revision: str,
    source_path: str,
    catalog: tuple[TrustedGitHubSourceDefinition, ...] | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
    resolve_host: Callable[[str, int], Awaitable[tuple[str, ...]]] = resolve_public_addresses,
) -> AcquiredTrustedEndpointSource:
    definitions = trusted_github_source_catalog_from_env() if catalog is None else catalog
    definition = _select_definition(source_identity_id, definitions)
    revision = _safe_revision(source_revision, error_code="trusted_source_commit_invalid")
    if revision not in definition.allowed_revisions:
        raise TrustedEndpointSourceAcquisitionError("trusted_source_revision_not_allowlisted")
    path = _safe_path(source_path)
    if not _path_allowed(path, definition.allowed_path_prefixes):
        raise TrustedEndpointSourceAcquisitionError("trusted_source_path_not_allowlisted")

    owner, repository = definition.repository.split("/", 1)
    url = f"https://{_RAW_GITHUB_HOST}/{owner}/{repository}/{revision}/{path}"
    await resolve_host(_RAW_GITHUB_HOST, 443)

    try:
        async with httpx.AsyncClient(
            transport=transport,
            timeout=httpx.Timeout(10.0),
            follow_redirects=False,
            trust_env=False,
        ) as client:
            async with client.stream(
                "GET",
                url,
                headers={"Accept": "application/octet-stream"},
            ) as response:
                if 300 <= response.status_code < 400:
                    raise TrustedEndpointSourceAcquisitionError(
                        "trusted_source_redirect_rejected"
                    )
                if response.status_code != 200:
                    raise TrustedEndpointSourceAcquisitionError(
                        "trusted_source_fetch_status_invalid"
                    )
                content = await _read_bounded_response(response)
    except TrustedEndpointSourceAcquisitionError:
        raise
    except httpx.HTTPError as exc:
        raise TrustedEndpointSourceAcquisitionError("trusted_source_fetch_failed") from exc

    document = _parse_api_description(content, path)
    digest = canonical_api_description_sha256(document)
    reference = f"github:{definition.repository}@{revision}:{path}"
    trusted_record = TrustedEndpointSourceRecord(
        source_identity_id=definition.source_identity_id,
        contract_family=definition.contract_family,
        source_reference=reference,
        source_kind="git_commit",
        source_revision=revision,
        source_sha256=digest,
        policy_version=definition.policy_version,
    )
    return AcquiredTrustedEndpointSource(
        api_description=document,
        trusted_record=trusted_record,
        repository=definition.repository,
        path=path,
    )


__all__ = [
    "AcquiredTrustedEndpointSource",
    "MAX_TRUSTED_SOURCE_BYTES",
    "TrustedEndpointSourceAcquisitionError",
    "TrustedGitHubSourceDefinition",
    "acquire_trusted_github_endpoint_source",
    "trusted_github_source_catalog_from_env",
]
