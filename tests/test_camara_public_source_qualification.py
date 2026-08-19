from __future__ import annotations

import httpx
import pytest

from processual_api.integrations.camara_public_source_qualification import (
    qualify_reviewed_camara_qod_public_source,
)
from processual_api.integrations.trusted_endpoint_source_acquisition import (
    CAMARA_QOD_R32_COMMIT,
)


async def _public_resolver(host: str, port: int) -> tuple[str, ...]:
    assert host == "raw.githubusercontent.com"
    assert port == 443
    return ("185.199.108.133",)


def _qod_root() -> bytes:
    return b"""openapi: 3.0.3
info:
  title: Quality-On-Demand
  version: 1.1.0
  x-extra: safe
x-camara-commonalities: 0.6
servers:
  - url: https://sandbox.example/quality-on-demand/v1
paths:
  /sessions:
    post:
      operationId: createSession
      security:
        - openId:
            - quality-on-demand:sessions:create
      requestBody:
        content:
          application/json:
            schema:
              $ref: ../common/CAMARA_common.yaml#/components/schemas/CloudEvent
      responses:
        '201':
          description: created
components:
  securitySchemes:
    openId:
      type: oauth2
      flows:
        clientCredentials:
          tokenUrl: https://auth.example/token
          scopes:
            quality-on-demand:sessions:create: create sessions
"""


def _common() -> bytes:
    return b"""components:
  schemas:
    CloudEvent:
      type: object
"""


@pytest.mark.asyncio
async def test_public_camara_runner_returns_safe_nonproduction_evidence() -> None:
    requested: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        requested.append(url)
        if url.endswith("/code/API_definitions/quality-on-demand.yaml"):
            return httpx.Response(200, content=_qod_root())
        if url.endswith("/code/common/CAMARA_common.yaml"):
            return httpx.Response(200, content=_common())
        return httpx.Response(404)

    evidence = await qualify_reviewed_camara_qod_public_source(
        transport=httpx.MockTransport(handler),
        resolve_host=_public_resolver,
    )

    assert all(f"/{CAMARA_QOD_R32_COMMIT}/" in url for url in requested)
    assert evidence["status"] == "public_standards_source_acquired"
    assert evidence["source_identity_id"] == "camara.quality_on_demand.r3_2"
    assert evidence["source_identity_verified"] is True
    assert evidence["external_references_resolved"] is True
    assert evidence["version"] == "1.1.0"
    assert evidence["contract_family"] == "camara"
    assert evidence["operation_count"] == 1
    assert evidence["discovery_quality_passed"] is True
    assert evidence["source_bundle_sha256"]
    assert evidence["source_bundle_paths"] == [
        "code/API_definitions/quality-on-demand.yaml",
        "code/common/CAMARA_common.yaml",
    ]
    assert evidence["production_allowed"] is False
    assert evidence["runtime_connector_approved"] is False
    assert evidence["provider_credentials_present"] is False
    assert evidence["provider_network_proof"] is False
    assert evidence["provider_sandbox_proven"] is False
    assert "api_description" not in evidence
    assert "paths" not in evidence


@pytest.mark.asyncio
async def test_public_camara_runner_fails_when_reviewed_bundle_cannot_be_acquired() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url).endswith("/code/API_definitions/quality-on-demand.yaml"):
            return httpx.Response(200, content=_qod_root())
        return httpx.Response(404)

    with pytest.raises(ValueError, match="trusted_source_fetch_status_invalid"):
        await qualify_reviewed_camara_qod_public_source(
            transport=httpx.MockTransport(handler),
            resolve_host=_public_resolver,
        )
