from __future__ import annotations

import hashlib
import json

import httpx
import pytest

from processual_api.integrations.endpoint_discovery_quality import (
    canonical_api_description_sha256,
)
from processual_api.integrations.trusted_endpoint_source_acquisition import (
    CAMARA_QOD_R32_COMMIT,
    CAMARA_QOD_R32_PATH,
    CAMARA_QOD_R32_QUALIFICATION_CANDIDATE,
    MAX_TRUSTED_SOURCE_BUNDLE_FILES,
    MAX_TRUSTED_SOURCE_REF_DEPTH,
    TrustedEndpointSourceAcquisitionError,
    TrustedGitHubSourceDefinition,
    acquire_trusted_github_endpoint_source,
)

COMMIT = "0123456789abcdef0123456789abcdef01234567"


async def _public_resolver(host: str, port: int) -> tuple[str, ...]:
    assert host == "raw.githubusercontent.com"
    assert port == 443
    return ("185.199.108.133",)


def _definition() -> TrustedGitHubSourceDefinition:
    return TrustedGitHubSourceDefinition(
        source_identity_id="standards.bundle",
        repository="standards/example-api",
        contract_family="generic_enterprise",
        allowed_path_prefixes=("openapi/releases",),
        allowed_revisions=(COMMIT,),
        allowed_reference_prefixes=("openapi/common",),
    )


def _root(ref: str) -> bytes:
    return (
        "openapi: 3.1.0\n"
        "info:\n  title: Bundle API\n  version: 1.0.0\n"
        "paths:\n"
        "  /health:\n"
        "    get:\n"
        "      operationId: getHealth\n"
        "      responses:\n"
        "        '200':\n"
        "          description: ok\n"
        f"          content:\n            application/json:\n              schema:\n                $ref: '{ref}'\n"
    ).encode()


def _common(next_ref: str | None = None) -> bytes:
    suffix = ""
    if next_ref is not None:
        suffix = f"\n  Next:\n    $ref: '{next_ref}'\n"
    return (
        "components:\n"
        "  schemas:\n"
        "    Health:\n"
        "      type: object\n"
        f"{suffix}"
    ).encode()


@pytest.mark.asyncio
async def test_camara_style_parent_reference_resolves_at_same_repo_and_commit() -> None:
    requested: list[str] = []
    root = _root("../common/CAMARA_common.yaml#/components/schemas/CloudEvent")
    common = _common()

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        if str(request.url).endswith("/code/API_definitions/quality-on-demand.yaml"):
            return httpx.Response(200, content=root)
        if str(request.url).endswith("/code/common/CAMARA_common.yaml"):
            return httpx.Response(200, content=common)
        return httpx.Response(404)

    acquired = await acquire_trusted_github_endpoint_source(
        source_identity_id=CAMARA_QOD_R32_QUALIFICATION_CANDIDATE.source_identity_id,
        source_revision=CAMARA_QOD_R32_COMMIT,
        source_path=CAMARA_QOD_R32_PATH,
        catalog=(CAMARA_QOD_R32_QUALIFICATION_CANDIDATE,),
        transport=httpx.MockTransport(handler),
        resolve_host=_public_resolver,
    )

    prefix = (
        "https://raw.githubusercontent.com/camaraproject/QualityOnDemand/"
        f"{CAMARA_QOD_R32_COMMIT}/"
    )
    assert requested == [
        prefix + "code/API_definitions/quality-on-demand.yaml",
        prefix + "code/common/CAMARA_common.yaml",
    ]
    assert acquired.external_references_resolved is True
    assert acquired.source_bundle_paths == (
        "code/API_definitions/quality-on-demand.yaml",
        "code/common/CAMARA_common.yaml",
    )
    assert acquired.source_bundle_sha256


@pytest.mark.parametrize(
    "reference,error",
    [
        ("https://evil.example/common.yaml#/x", "external_rejected"),
        ("//evil.example/common.yaml#/x", "external_rejected"),
        ("../../../secret.yaml#/x", "repository_escape"),
        ("../drafts/common.yaml#/x", "path_not_allowlisted"),
        ("../common/%2e%2e/secret.yaml#/x", "external_rejected"),
    ],
)
@pytest.mark.asyncio
async def test_unsafe_or_non_allowlisted_refs_are_rejected_without_ref_network(
    reference: str,
    error: str,
) -> None:
    requests = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        if requests > 1:
            raise AssertionError("rejected reference must not reach network")
        return httpx.Response(200, content=_root(reference))

    with pytest.raises(TrustedEndpointSourceAcquisitionError, match=error):
        await acquire_trusted_github_endpoint_source(
            source_identity_id="standards.bundle",
            source_revision=COMMIT,
            source_path="openapi/releases/v1/openapi.yaml",
            catalog=(_definition(),),
            transport=httpx.MockTransport(handler),
            resolve_host=_public_resolver,
        )

    assert requests == 1


@pytest.mark.asyncio
async def test_fragment_only_refs_do_not_fetch_another_document() -> None:
    requests = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        return httpx.Response(200, content=_root("#/components/schemas/Health"))

    acquired = await acquire_trusted_github_endpoint_source(
        source_identity_id="standards.bundle",
        source_revision=COMMIT,
        source_path="openapi/releases/v1/openapi.yaml",
        catalog=(_definition(),),
        transport=httpx.MockTransport(handler),
        resolve_host=_public_resolver,
    )

    assert requests == 1
    assert acquired.external_references_resolved is False
    assert acquired.source_bundle_paths == ("openapi/releases/v1/openapi.yaml",)


@pytest.mark.asyncio
async def test_reference_cycle_is_deduplicated() -> None:
    requested: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        requested.append(url)
        if url.endswith("/openapi/releases/v1/openapi.yaml"):
            return httpx.Response(200, content=_root("../../common/a.yaml#/components/schemas/A"))
        if url.endswith("/openapi/common/a.yaml"):
            return httpx.Response(200, content=_common("b.yaml#/components/schemas/Health"))
        if url.endswith("/openapi/common/b.yaml"):
            return httpx.Response(200, content=_common("a.yaml#/components/schemas/Health"))
        return httpx.Response(404)

    acquired = await acquire_trusted_github_endpoint_source(
        source_identity_id="standards.bundle",
        source_revision=COMMIT,
        source_path="openapi/releases/v1/openapi.yaml",
        catalog=(_definition(),),
        transport=httpx.MockTransport(handler),
        resolve_host=_public_resolver,
    )

    assert len(requested) == 3
    assert acquired.source_bundle_paths == (
        "openapi/common/a.yaml",
        "openapi/common/b.yaml",
        "openapi/releases/v1/openapi.yaml",
    )


@pytest.mark.asyncio
async def test_reference_depth_limit_fails_closed() -> None:
    requests = 0

    definition = TrustedGitHubSourceDefinition(
        source_identity_id="standards.bundle",
        repository="standards/example-api",
        contract_family="generic_enterprise",
        allowed_path_prefixes=("openapi/releases",),
        allowed_revisions=(COMMIT,),
        allowed_reference_prefixes=("openapi/common",),
    )

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        path = str(request.url).split(f"/{COMMIT}/", 1)[1]
        if path == "openapi/releases/v1/openapi.yaml":
            return httpx.Response(200, content=_root("../../common/0.yaml#/x"))
        index = int(path.rsplit("/", 1)[1].split(".", 1)[0])
        return httpx.Response(200, content=_common(f"{index + 1}.yaml#/x"))

    with pytest.raises(TrustedEndpointSourceAcquisitionError, match="ref_depth_exceeded"):
        await acquire_trusted_github_endpoint_source(
            source_identity_id="standards.bundle",
            source_revision=COMMIT,
            source_path="openapi/releases/v1/openapi.yaml",
            catalog=(definition,),
            transport=httpx.MockTransport(handler),
            resolve_host=_public_resolver,
        )

    assert requests == MAX_TRUSTED_SOURCE_REF_DEPTH + 1


@pytest.mark.asyncio
async def test_bundle_file_limit_fails_closed() -> None:
    references = "\n".join(
        f"      item{index}:\n        $ref: '../../common/{index}.yaml#/x'"
        for index in range(MAX_TRUSTED_SOURCE_BUNDLE_FILES)
    )
    root = (
        "openapi: 3.1.0\n"
        "info: {title: Bundle API, version: 1.0.0}\n"
        "paths: {}\n"
        "components:\n"
        "  schemas:\n"
        f"{references}\n"
    ).encode()

    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url).endswith("/openapi/releases/v1/openapi.yaml"):
            return httpx.Response(200, content=root)
        return httpx.Response(200, content=_common())

    with pytest.raises(TrustedEndpointSourceAcquisitionError, match="bundle_file_limit"):
        await acquire_trusted_github_endpoint_source(
            source_identity_id="standards.bundle",
            source_revision=COMMIT,
            source_path="openapi/releases/v1/openapi.yaml",
            catalog=(_definition(),),
            transport=httpx.MockTransport(handler),
            resolve_host=_public_resolver,
        )


@pytest.mark.asyncio
async def test_bundle_digest_is_deterministic_from_sorted_path_digest_manifest() -> None:
    root = (
        b"openapi: 3.1.0\n"
        b"info: {title: Bundle API, version: 1.0.0}\n"
        b"paths: {}\n"
        b"components:\n"
        b"  schemas:\n"
        b"    B: {$ref: '../../common/b.yaml#/x'}\n"
        b"    A: {$ref: '../../common/a.yaml#/x'}\n"
    )
    documents = {
        "openapi/releases/v1/openapi.yaml": root,
        "openapi/common/a.yaml": _common(),
        "openapi/common/b.yaml": _common(),
    }

    def handler(request: httpx.Request) -> httpx.Response:
        path = str(request.url).split(f"/{COMMIT}/", 1)[1]
        return httpx.Response(200, content=documents[path])

    acquired = await acquire_trusted_github_endpoint_source(
        source_identity_id="standards.bundle",
        source_revision=COMMIT,
        source_path="openapi/releases/v1/openapi.yaml",
        catalog=(_definition(),),
        transport=httpx.MockTransport(handler),
        resolve_host=_public_resolver,
    )

    parsed = {
        path: __import__("yaml").safe_load(content.decode())
        for path, content in documents.items()
    }
    manifest = [
        [path, canonical_api_description_sha256(document)]
        for path, document in sorted(parsed.items())
    ]
    expected = hashlib.sha256(
        json.dumps(manifest, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()
    assert acquired.source_bundle_sha256 == expected
