"""Read-only OpenAPI/Swagger endpoint discovery and quality assessment.

This module deliberately does not fetch specifications or execute network
requests. A caller must provide a parsed, review-pinned API document. The output
is an inventory of candidate operations plus fail-closed blockers that must be
cleared before an operation is eligible for an Enterprise endpoint binding.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from typing import Any

_HTTP_METHODS = ("get", "post", "put", "patch", "delete", "head", "options")
_VERSIONED_SERVER = re.compile(r"/v(?:wip|\d[0-9a-z.-]*)", re.IGNORECASE)


class EndpointDiscoveryError(ValueError):
    """The supplied API description cannot be safely inventoried."""


def _digest(document: Mapping[str, Any]) -> str:
    payload = json.dumps(
        document,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _api_dialect(document: Mapping[str, Any]) -> str:
    openapi = str(document.get("openapi") or "").strip()
    swagger = str(document.get("swagger") or "").strip()
    if openapi.startswith("3.0"):
        return "openapi_3_0"
    if openapi.startswith("3.1"):
        return "openapi_3_1"
    if swagger == "2.0":
        return "swagger_2_0"
    raise EndpointDiscoveryError("unsupported_api_description_dialect")


def _external_refs(value: Any) -> set[str]:
    refs: set[str] = set()
    if isinstance(value, Mapping):
        ref = value.get("$ref")
        if isinstance(ref, str) and ref and not ref.startswith("#/"):
            refs.add(ref)
        for nested in value.values():
            refs.update(_external_refs(nested))
    elif isinstance(value, list):
        for nested in value:
            refs.update(_external_refs(nested))
    return refs


def _operation_security(
    operation: Mapping[str, Any],
    root_security: Any,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    security = operation.get("security", root_security)
    schemes: set[str] = set()
    scopes: set[str] = set()
    if not isinstance(security, list):
        return (), ()
    for requirement in security:
        if not isinstance(requirement, Mapping):
            continue
        for raw_scheme, values in requirement.items():
            scheme = str(raw_scheme or "").strip()
            if scheme:
                schemes.add(scheme)
            if isinstance(values, list):
                scopes.update(str(value).strip() for value in values if str(value).strip())
    return tuple(sorted(schemes)), tuple(sorted(scopes))


def _defined_security_schemes(
    document: Mapping[str, Any],
    dialect: str,
) -> set[str]:
    if dialect.startswith("openapi_"):
        components = document.get("components")
        if not isinstance(components, Mapping):
            return set()
        definitions = components.get("securitySchemes")
    else:
        definitions = document.get("securityDefinitions")
    if not isinstance(definitions, Mapping):
        return set()
    return {str(name).strip() for name in definitions if str(name).strip()}


def _swagger_media_types(
    operation: Mapping[str, Any],
    document: Mapping[str, Any],
    key: str,
) -> tuple[str, ...]:
    values = operation.get(key) if key in operation else document.get(key)
    if not isinstance(values, list):
        return ()
    return tuple(sorted(str(value).strip() for value in values if str(value).strip()))


def _request_media_types(
    operation: Mapping[str, Any],
    document: Mapping[str, Any],
    dialect: str,
) -> tuple[str, ...]:
    if dialect.startswith("openapi_"):
        body = operation.get("requestBody")
        if not isinstance(body, Mapping):
            return ()
        content = body.get("content")
        if not isinstance(content, Mapping):
            return ()
        return tuple(sorted(str(key) for key in content))
    return _swagger_media_types(operation, document, "consumes")


def _response_media_types(
    operation: Mapping[str, Any],
    document: Mapping[str, Any],
    dialect: str,
) -> tuple[str, ...]:
    responses = operation.get("responses")
    if not isinstance(responses, Mapping):
        return ()
    media: set[str] = set()
    if dialect.startswith("openapi_"):
        for response in responses.values():
            if not isinstance(response, Mapping):
                continue
            content = response.get("content")
            if isinstance(content, Mapping):
                media.update(str(key) for key in content)
    else:
        media.update(_swagger_media_types(operation, document, "produces"))
    return tuple(sorted(media))


def _path_parameter_names(path: str) -> set[str]:
    return set(re.findall(r"\{([^{}]+)\}", path))


def _declared_path_parameters(
    path_item: Mapping[str, Any],
    operation: Mapping[str, Any],
) -> dict[str, bool]:
    result: dict[str, bool] = {}
    for source in (path_item.get("parameters"), operation.get("parameters")):
        if not isinstance(source, list):
            continue
        for parameter in source:
            if not isinstance(parameter, Mapping) or parameter.get("in") != "path":
                continue
            name = str(parameter.get("name") or "").strip()
            if name:
                result[name] = parameter.get("required") is True
    return result


def _server_hints(document: Mapping[str, Any], dialect: str) -> tuple[str, ...]:
    if dialect.startswith("openapi_"):
        servers = document.get("servers")
        if not isinstance(servers, list):
            return ()
        return tuple(
            str(server.get("url") or "").strip()
            for server in servers
            if isinstance(server, Mapping) and str(server.get("url") or "").strip()
        )
    base_path = str(document.get("basePath") or "").strip()
    return (base_path,) if base_path else ()


def _operation_inventory(
    document: Mapping[str, Any],
    *,
    dialect: str,
) -> tuple[list[dict[str, Any]], list[str]]:
    paths = document.get("paths")
    if not isinstance(paths, Mapping) or not paths:
        raise EndpointDiscoveryError("api_description_paths_required")

    root_security = document.get("security")
    defined_security_schemes = _defined_security_schemes(document, dialect)
    operations: list[dict[str, Any]] = []
    operation_ids: list[str] = []

    for raw_path, raw_item in paths.items():
        path = str(raw_path or "").strip()
        if not path.startswith("/") or path.startswith("//") or "://" in path:
            raise EndpointDiscoveryError("unsafe_api_path")
        if not isinstance(raw_item, Mapping):
            continue
        for method in _HTTP_METHODS:
            raw_operation = raw_item.get(method)
            if not isinstance(raw_operation, Mapping):
                continue
            operation_id = str(raw_operation.get("operationId") or "").strip()
            if operation_id:
                operation_ids.append(operation_id)
            expected_path_params = _path_parameter_names(path)
            declared_path_params = _declared_path_parameters(raw_item, raw_operation)
            missing_path_params = sorted(expected_path_params - set(declared_path_params))
            optional_path_params = sorted(
                name for name in expected_path_params if declared_path_params.get(name) is not True
            )
            responses = raw_operation.get("responses")
            response_codes = (
                tuple(sorted(str(code) for code in responses))
                if isinstance(responses, Mapping)
                else ()
            )
            security_schemes, security_scopes = _operation_security(
                raw_operation,
                root_security,
            )
            undefined_security_schemes = sorted(
                set(security_schemes) - defined_security_schemes
            )
            operations.append(
                {
                    "operation_id": operation_id or None,
                    "method": method.upper(),
                    "path": path,
                    "summary": str(raw_operation.get("summary") or "").strip() or None,
                    "tags": [str(tag) for tag in raw_operation.get("tags", [])]
                    if isinstance(raw_operation.get("tags"), list)
                    else [],
                    "security_schemes": list(security_schemes),
                    "security_scopes": list(security_scopes),
                    "undefined_security_schemes": undefined_security_schemes,
                    "request_media_types": list(
                        _request_media_types(raw_operation, document, dialect)
                    ),
                    "response_media_types": list(
                        _response_media_types(raw_operation, document, dialect)
                    ),
                    "response_codes": list(response_codes),
                    "path_parameters": sorted(expected_path_params),
                    "missing_path_parameter_declarations": missing_path_params,
                    "non_required_path_parameters": optional_path_params,
                    "external_reference_count": len(_external_refs(raw_operation)),
                }
            )

    if not operations:
        raise EndpointDiscoveryError("api_description_operations_required")
    return operations, operation_ids


def assess_endpoint_discovery(
    document: Mapping[str, Any],
    *,
    contract_family: str,
    source_reference: str,
    release_pinned: bool,
    external_references_resolved: bool,
) -> dict[str, Any]:
    """Inventory operations and determine whether binding generation is safe.

    `source_reference` is provenance only (for example a repository tag and file
    path); it is never fetched here. `release_pinned` must be supplied by the
    caller after selecting an immutable/reviewed release instead of a moving
    branch such as `main`.
    """

    if not isinstance(document, Mapping):
        raise EndpointDiscoveryError("api_description_mapping_required")
    family = str(contract_family or "").strip().lower().replace("-", "_")
    if family not in {"camara", "tm_forum", "proprietary", "legacy", "generic_enterprise"}:
        raise EndpointDiscoveryError("unsupported_contract_family")
    provenance = str(source_reference or "").strip()
    if not provenance:
        raise EndpointDiscoveryError("source_reference_required")

    dialect = _api_dialect(document)
    info = document.get("info")
    if not isinstance(info, Mapping):
        raise EndpointDiscoveryError("api_description_info_required")
    title = str(info.get("title") or "").strip()
    version = str(info.get("version") or "").strip()
    if not title or not version:
        raise EndpointDiscoveryError("api_title_and_version_required")

    operations, operation_ids = _operation_inventory(document, dialect=dialect)
    duplicate_operation_ids = sorted(
        operation_id for operation_id in set(operation_ids)
        if operation_ids.count(operation_id) > 1
    )
    missing_operation_id_count = sum(
        operation["operation_id"] is None for operation in operations
    )
    path_parameter_blockers = sum(
        bool(operation["missing_path_parameter_declarations"])
        or bool(operation["non_required_path_parameters"])
        for operation in operations
    )
    undefined_security_schemes = sorted(
        {
            scheme
            for operation in operations
            for scheme in operation["undefined_security_schemes"]
        }
    )
    external_refs = sorted(_external_refs(document))
    server_hints = _server_hints(document, dialect)

    blockers: list[str] = []
    warnings: list[str] = []
    if not release_pinned:
        blockers.append("immutable_release_source_required")
    if duplicate_operation_ids:
        blockers.append("duplicate_operation_id")
    if missing_operation_id_count:
        blockers.append("operation_id_required")
    if path_parameter_blockers:
        blockers.append("path_parameter_contract_invalid")
    if undefined_security_schemes:
        blockers.append("security_scheme_definition_required")
    if external_refs and not external_references_resolved:
        blockers.append("external_schema_references_must_be_resolved")

    if family == "camara":
        if not dialect.startswith("openapi_"):
            blockers.append("camara_requires_openapi_3")
        if version.casefold() == "wip":
            blockers.append("camara_wip_version_not_qualifiable")
        commonalities = str(document.get("x-camara-commonalities") or "").strip()
        if not commonalities:
            blockers.append("camara_commonalities_version_required")
        if not server_hints or not any(_VERSIONED_SERVER.search(server) for server in server_hints):
            blockers.append("camara_versioned_server_contract_required")
        if not any(operation["security_scopes"] for operation in operations):
            warnings.append("camara_security_scopes_not_explicit_in_inventory")
    elif family == "tm_forum":
        if dialect not in {"openapi_3_0", "openapi_3_1", "swagger_2_0"}:
            blockers.append("tm_forum_supported_dialect_required")

    for operation in operations:
        if operation["method"] in {"POST", "PUT", "PATCH"} and not operation[
            "request_media_types"
        ]:
            warnings.append(
                f"request_media_type_not_declared:{operation['method']}:{operation['path']}"
            )
        if not operation["response_codes"]:
            blockers.append(
                f"response_contract_required:{operation['method']}:{operation['path']}"
            )

    blockers = sorted(set(blockers))
    warnings = sorted(set(warnings))
    return {
        "source": "parsed_api_description",
        "source_reference": provenance,
        "source_sha256": _digest(document),
        "title": title,
        "version": version,
        "dialect": dialect,
        "contract_family": family,
        "operation_count": len(operations),
        "operations": operations,
        "defined_security_schemes": sorted(_defined_security_schemes(document, dialect)),
        "undefined_security_schemes": undefined_security_schemes,
        "external_references": external_refs,
        "external_reference_count": len(external_refs),
        "external_references_resolved": external_references_resolved,
        "server_hints": list(server_hints),
        "duplicate_operation_ids": duplicate_operation_ids,
        "missing_operation_id_count": missing_operation_id_count,
        "blocker_codes": blockers,
        "warning_codes": warnings,
        "discovery_quality_passed": not blockers,
        "binding_generation_ready": not blockers,
        "network_request_executed": False,
        "production_allowed": False,
        "runtime_connector_approved": False,
        "raw_secret_visible": False,
    }


__all__ = [
    "EndpointDiscoveryError",
    "assess_endpoint_discovery",
]
