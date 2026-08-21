from __future__ import annotations

import json

import httpx
import pytest

from processual_api.integrations.endpoint_source_attestation import (
    attest_endpoint_source_identity,
)
from processual_api.integrations.trusted_endpoint_source_acquisition import (
    CAMARA_QOD_R32_COMMIT,
    CAMARA_QOD_R32_PATH,
    CAMARA_QOD_R32_QUALIFICATION_CANDIDATE,
    MAX_TRUSTED_SOURCE_BYTES,
    TrustedEndpointSourceAcquisitionError,
    TrustedGitHubSourceDefinition,
    acquire_trusted_github_endpoint_source,
    trusted_github_source_catalog_from_env,
)

COMMIT = "0123456789abcdef0123456789abcdef01234567"
OTHER_COMMIT = "89abcdef0123456789abcdef0123456789abcdef"


def _catalog() -> tuple[TrustedGitHubSourceDefinition, ...]:
    return (
        TrustedGitHubSourceDefinition(
            source_identity_id="standards.example",
            repository="standards/example-api",
            contract_family="generic_enterprise",
            allowed_path_prefixes=("openapi/releases",),
            allowed_revisions=(COMMIT,),
        ),
    )


async def _public_resolver(host: str, port: int) -> tuple[str, ...]:
    assert host == "raw.githubusercontent.com"
    assert port == 443
    return ("185.199.108.133",)


def _openapi_json() -> bytes:
    return json.dumps(
        {
            "openapi": "3.1.0",
            "info": {"title": "Trusted API", "version": "1.0.0"},
            "paths": {
                "/health": {
                    "get": {
                        "operationId": "getHealth",
                        "responses": {"200": {"description": "ok"}},
                    }
                }
            },
        }
    ).encode("utf-8")


def test_camara_qod_r32_candidate_is_exact_but_not_runtime_enabled(monkeypatch) -> None:
    monkeypatch.delenv("PMK_TRUSTED_GITHUB_ENDPOINT_SOURCES", raising=False)
    candidate = CAMARA_QOD_R32_QUALIFICATION_CANDIDATE

    assert candidate.source_identity_id == "camara.quality_on_demand.r3_2"
    assert candidate.repository == "camaraproject/QualityOnDemand"
    assert candidate.contract_family == "camara"
    assert candidate.allowed_path_prefixes == ("code/API_definitions",)
    assert candidate.allowed_revisions == (CAMARA_QOD_R32_COMMIT,)
    assert candidate.policy_version == "camara-public-release-review-r1"
    assert CAMARA_QOD_R32_PATH == "code/API_definitions/quality-on-demand.yaml"
    assert trusted_github_source_catalog_from_env() == ()


@pytest.mark.asyncio
async def test_camara_candidate_can_only_acquire_its_reviewed_revision_and_path() -> None:
    body = b"""openapi: 3.0.3
info:
  title: Quality-On-Demand
  version: 1.1.0
paths: {}
"""
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, content=body)

    acquired = await acquire_trusted_github_endpoint_source(
        source_identity_id=CAMARA_QOD_R32_QUALIFICATION_CANDIDATE.source_identity_id,
        source_revision=CAMARA_QOD_R32_COMMIT,
        source_path=CAMARA_QOD_R32_PATH,
        catalog=(CAMARA_QOD_R32_QUALIFICATION_CANDIDATE,),
        transport=httpx.MockTransport(handler),
        resolve_host=_public_resolver,
    )

    assert seen["url"] == (
        "https://raw.githubusercontent.com/camaraproject/QualityOnDemand/"
        f"{CAMARA_QOD_R32_COMMIT}/{CAMARA_QOD_R32_PATH}"
    )
    assert acquired.api_description["info"]["version"] == "1.1.0"
    assert acquired.trusted_record.source_identity_id == "camara.quality_on_demand.r3_2"
    assert acquired.trusted_record.contract_family == "camara"
    assert acquired.production_allowed is False
    assert acquired.runtime_connector_approved is False


@pytest.mark.asyncio
async def test_acquisition_builds_fixed_github_target_and_trusted_record() -> None:
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        assert request.headers["accept"] == "application/octet-stream"
        return httpx.Response(200, content=_openapi_json())

    acquired = await acquire_trusted_github_endpoint_source(
        source_identity_id="standards.example",
        source_revision=COMMIT,
        source_path="openapi/releases/v1/openapi.json",
        catalog=_catalog(),
        transport=httpx.MockTransport(handler),
        resolve_host=_public_resolver,
    )

    assert seen["url"] == (
        "https://raw.githubusercontent.com/standards/example-api/"
        f"{COMMIT}/openapi/releases/v1/openapi.json"
    )
    assert acquired.repository == "standards/example-api"
    assert acquired.trusted_record.source_reference == (
        f"github:standards/example-api@{COMMIT}:openapi/releases/v1/openapi.json"
    )
    assert acquired.trusted_record.source_kind == "git_commit"
    assert acquired.trusted_record.source_revision == COMMIT
    assert acquired.trusted_record.source_sha256
    assert acquired.production_allowed is False
    assert acquired.runtime_connector_approved is False

    attestation = attest_endpoint_source_identity(
        source_reference=acquired.trusted_record.source_reference,
        source_kind=acquired.trusted_record.source_kind,
        source_revision=acquired.trusted_record.source_revision,
        source_sha256=acquired.trusted_record.source_sha256,
        contract_family=acquired.trusted_record.contract_family,
        trusted_sources=[acquired.trusted_record],
    )
    assert attestation.source_identity_verified is True
    assert attestation.source_identity_id == "standards.example"


@pytest.mark.asyncio
async def test_yaml_is_parsed_from_allowlisted_immutable_source() -> None:
    body = b"""openapi: 3.0.3
info:
  title: Trusted YAML API
  version: 1.2.0
paths:
  /health:
    get:
      operationId: getHealth
      responses:
        '200':
          description: ok
"""

    acquired = await acquire_trusted_github_endpoint_source(
        source_identity_id="standards.example",
        source_revision=COMMIT,
        source_path="openapi/releases/v1/openapi.yaml",
        catalog=_catalog(),
        transport=httpx.MockTransport(lambda _request: httpx.Response(200, content=body)),
        resolve_host=_public_resolver,
    )

    assert acquired.api_description["openapi"] == "3.0.3"
    assert acquired.api_description["info"]["version"] == "1.2.0"


@pytest.mark.parametrize(
    "path",
    [
        "../openapi.json",
        "openapi/releases/../../secret.json",
        "openapi/releases/v1/openapi.json?raw=1",
        "openapi/releases/v1/openapi.json#fragment",
        "openapi/releases/v1/%2e%2e/secret.json",
        "openapi\\releases\\v1\\openapi.json",
        "/openapi/releases/v1/openapi.json",
    ],
)
@pytest.mark.asyncio
async def test_path_injection_is_rejected_before_network(path: str) -> None:
    async def no_network(_host: str, _port: int) -> tuple[str, ...]:
        raise AssertionError("unsafe path must be rejected before DNS/network")

    with pytest.raises(TrustedEndpointSourceAcquisitionError, match="trusted_source_path_invalid"):
        await acquire_trusted_github_endpoint_source(
            source_identity_id="standards.example",
            source_revision=COMMIT,
            source_path=path,
            catalog=_catalog(),
            transport=httpx.MockTransport(
                lambda _request: (_ for _ in ()).throw(AssertionError("network must not run"))
            ),
            resolve_host=no_network,
        )


@pytest.mark.asyncio
async def test_non_allowlisted_path_is_rejected_before_network() -> None:
    async def no_network(_host: str, _port: int) -> tuple[str, ...]:
        raise AssertionError("non-allowlisted path must not resolve")

    with pytest.raises(TrustedEndpointSourceAcquisitionError, match="path_not_allowlisted"):
        await acquire_trusted_github_endpoint_source(
            source_identity_id="standards.example",
            source_revision=COMMIT,
            source_path="drafts/openapi.json",
            catalog=_catalog(),
            resolve_host=no_network,
        )


@pytest.mark.asyncio
async def test_moving_ref_is_rejected_before_network() -> None:
    async def no_network(_host: str, _port: int) -> tuple[str, ...]:
        raise AssertionError("moving ref must not resolve")

    with pytest.raises(TrustedEndpointSourceAcquisitionError, match="commit_invalid"):
        await acquire_trusted_github_endpoint_source(
            source_identity_id="standards.example",
            source_revision="main",
            source_path="openapi/releases/v1/openapi.json",
            catalog=_catalog(),
            resolve_host=no_network,
        )


@pytest.mark.asyncio
async def test_unapproved_immutable_revision_is_rejected_before_network() -> None:
    async def no_network(_host: str, _port: int) -> tuple[str, ...]:
        raise AssertionError("unapproved revision must not resolve")

    with pytest.raises(
        TrustedEndpointSourceAcquisitionError,
        match="revision_not_allowlisted",
    ):
        await acquire_trusted_github_endpoint_source(
            source_identity_id="standards.example",
            source_revision=OTHER_COMMIT,
            source_path="openapi/releases/v1/openapi.json",
            catalog=_catalog(),
            resolve_host=no_network,
        )


@pytest.mark.asyncio
async def test_redirect_is_rejected_and_not_followed() -> None:
    requests: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(str(request.url))
        return httpx.Response(302, headers={"Location": "https://evil.example/spec.json"})

    with pytest.raises(TrustedEndpointSourceAcquisitionError, match="redirect_rejected"):
        await acquire_trusted_github_endpoint_source(
            source_identity_id="standards.example",
            source_revision=COMMIT,
            source_path="openapi/releases/v1/openapi.json",
            catalog=_catalog(),
            transport=httpx.MockTransport(handler),
            resolve_host=_public_resolver,
        )

    assert len(requests) == 1
    assert requests[0].startswith("https://raw.githubusercontent.com/")


@pytest.mark.asyncio
async def test_oversize_response_is_rejected() -> None:
    body = b"{" + b" " * MAX_TRUSTED_SOURCE_BYTES + b"}"
    with pytest.raises(TrustedEndpointSourceAcquisitionError, match="size_invalid"):
        await acquire_trusted_github_endpoint_source(
            source_identity_id="standards.example",
            source_revision=COMMIT,
            source_path="openapi/releases/v1/openapi.json",
            catalog=_catalog(),
            transport=httpx.MockTransport(lambda _request: httpx.Response(200, content=body)),
            resolve_host=_public_resolver,
        )


@pytest.mark.asyncio
async def test_streaming_cutoff_stops_consuming_after_limit_is_crossed() -> None:
    class GuardedStream(httpx.AsyncByteStream):
        def __init__(self) -> None:
            self.yielded = 0

        async def __aiter__(self):
            self.yielded += 1
            yield b"{" + b" " * (MAX_TRUSTED_SOURCE_BYTES - 1)
            self.yielded += 1
            yield b"x"
            raise AssertionError("stream must stop immediately after crossing the size limit")

    stream = GuardedStream()

    with pytest.raises(TrustedEndpointSourceAcquisitionError, match="size_invalid"):
        await acquire_trusted_github_endpoint_source(
            source_identity_id="standards.example",
            source_revision=COMMIT,
            source_path="openapi/releases/v1/openapi.json",
            catalog=_catalog(),
            transport=httpx.MockTransport(
                lambda _request: httpx.Response(200, stream=stream)
            ),
            resolve_host=_public_resolver,
        )

    assert stream.yielded == 2


def test_catalog_is_server_owned_environment_configuration(monkeypatch) -> None:
    monkeypatch.setenv(
        "PMK_TRUSTED_GITHUB_ENDPOINT_SOURCES",
        json.dumps(
            [
                {
                    "source_identity_id": "camara.project",
                    "repository": "camaraproject/example",
                    "contract_family": "camara",
                    "allowed_path_prefixes": ["code/API_definitions"],
                    "allowed_revisions": [COMMIT],
                    "policy_version": "operator-reviewed-r2",
                }
            ]
        ),
    )

    catalog = trusted_github_source_catalog_from_env()
    assert len(catalog) == 1
    assert catalog[0].source_identity_id == "camara.project"
    assert catalog[0].repository == "camaraproject/example"
    assert catalog[0].contract_family == "camara"
    assert catalog[0].allowed_path_prefixes == ("code/API_definitions",)
    assert catalog[0].allowed_revisions == (COMMIT,)


def test_catalog_requires_explicit_approved_revisions(monkeypatch) -> None:
    monkeypatch.setenv(
        "PMK_TRUSTED_GITHUB_ENDPOINT_SOURCES",
        json.dumps(
            [
                {
                    "source_identity_id": "standards.example",
                    "repository": "standards/example-api",
                    "contract_family": "generic_enterprise",
                    "allowed_path_prefixes": ["openapi/releases"],
                }
            ]
        ),
    )

    with pytest.raises(TrustedEndpointSourceAcquisitionError, match="revisions_required"):
        trusted_github_source_catalog_from_env()


def test_catalog_rejects_duplicate_approved_revision(monkeypatch) -> None:
    monkeypatch.setenv(
        "PMK_TRUSTED_GITHUB_ENDPOINT_SOURCES",
        json.dumps(
            [
                {
                    "source_identity_id": "standards.example",
                    "repository": "standards/example-api",
                    "contract_family": "generic_enterprise",
                    "allowed_path_prefixes": ["openapi/releases"],
                    "allowed_revisions": [COMMIT, COMMIT],
                }
            ]
        ),
    )

    with pytest.raises(TrustedEndpointSourceAcquisitionError, match="duplicate_revision"):
        trusted_github_source_catalog_from_env()


def test_catalog_rejects_duplicate_identity(monkeypatch) -> None:
    item = {
        "source_identity_id": "standards.example",
        "repository": "standards/example-api",
        "contract_family": "generic_enterprise",
        "allowed_path_prefixes": ["openapi/releases"],
        "allowed_revisions": [COMMIT],
    }
    monkeypatch.setenv("PMK_TRUSTED_GITHUB_ENDPOINT_SOURCES", json.dumps([item, item]))

    with pytest.raises(TrustedEndpointSourceAcquisitionError, match="duplicate_identity"):
        trusted_github_source_catalog_from_env()
