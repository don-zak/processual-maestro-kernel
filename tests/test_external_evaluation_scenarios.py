from __future__ import annotations

from hashlib import sha256
from json import dumps

import pytest

from processual_api.integrations.sandbox_operational_readiness import (
    SandboxContentContract,
    SandboxSecretReference,
    safe_content_projection,
    safe_secret_reference_projection,
    sandbox_provisioning_fingerprint,
)
from processual_api.routers import evaluation_runtime_scenarios as scenarios_runtime
from processual_api.routers import settings_admin_evaluation_owned_sandbox_preset as owned_preset
from processual_api.services.evaluation_scenarios import customer_evaluation_scenarios


def _grant(*, endpoints=None, bindings=None, tasks=None):
    return {
        "allowed_task_ids": tasks or ["crm.customer_context"],
        "allowed_binding_ids": bindings or [],
        "allowed_endpoints": endpoints or [{"method": "POST", "path": "/cgt/govern"}],
    }


def test_scenario_never_widens_grant_authority() -> None:
    raw = {
        "enterprise_endpoint_bindings_v1": [
            {
                "binding_id": "crm.context.eval",
                "task_id": "crm.customer_context",
            }
        ]
    }
    scenarios = customer_evaluation_scenarios(raw, _grant())
    assert len(scenarios) == 1
    scenario = scenarios[0]
    assert scenario["scenario_id"] == "CRM-CONTEXT-01"
    assert scenario["runnable"] is False
    assert scenario["readiness"] == "runtime_endpoint_required"
    assert scenario["binding_ids"] == []
    assert scenario["production_allowed"] is False
    assert scenario["raw_secret_visible"] is False


def test_scenario_is_runnable_only_with_sealed_runtime_endpoint_and_matching_binding() -> None:
    raw = {
        "enterprise_endpoint_bindings_v1": [
            {
                "binding_id": "crm.context.eval",
                "task_id": "crm.customer_context",
            },
            {
                "binding_id": "billing.unrelated",
                "task_id": "billing.account_context",
            },
        ]
    }
    grant = _grant(
        endpoints=[{"method": "POST", "path": "/evaluation/runtime/task-execute"}],
        bindings=["crm.context.eval", "billing.unrelated"],
    )
    scenario = customer_evaluation_scenarios(raw, grant)[0]
    assert scenario["runnable"] is True
    assert scenario["readiness"] == "ready"
    assert scenario["binding_ids"] == ["crm.context.eval"]
    assert scenario["quota_cost_new_execution"] == 1
    assert scenario["quota_cost_replay"] == 0


def test_scenario_catalog_exposes_only_tasks_sealed_into_grant() -> None:
    raw = {"enterprise_endpoint_bindings_v1": []}
    grant = _grant(tasks=["crm.customer_state_summary"])
    scenarios = customer_evaluation_scenarios(raw, grant)
    assert [item["task_id"] for item in scenarios] == ["crm.customer_state_summary"]
    assert all("api_key" not in item for item in scenarios)
    assert all("secret" not in item for item in scenarios)


def test_project_owned_sandbox_content_is_explicit_and_customer_safe() -> None:
    contract = SandboxContentContract(
        binding_id="evaluation.crm.public",
        dataset_reference="project-evaluation-sandbox-customer-v1",
        fixture_profile_reference="crm-context-read-only-v1",
        required_record_types=("crm_customer",),
        acceptance_criteria_references=("CRM-CONTEXT-01",),
        customer_owned=False,
        project_owned=True,
        synthetic_or_nonproduction=True,
        secrets_included=False,
        raw_payloads_included=False,
    )

    safe = safe_content_projection(contract)
    assert safe["customer_owned"] is False
    assert safe["project_owned"] is True
    assert safe["content_owner"] == "project"
    assert safe["synthetic_or_nonproduction"] is True
    assert safe["secrets_included"] is False
    assert safe["raw_payloads_included"] is False
    assert safe["production_allowed"] is False


def test_project_owned_anonymous_reference_is_explicit_and_secret_free() -> None:
    reference = SandboxSecretReference(
        binding_id="evaluation.crm.public",
        provider_id="anonymous",
        secret_reference="public",
        customer_scoped=False,
        project_scoped=True,
        value_included=False,
    )

    safe = safe_secret_reference_projection(reference)
    assert safe["customer_scoped"] is False
    assert safe["project_scoped"] is True
    assert safe["reference_scope"] == "project"
    assert safe["value_included"] is False
    assert safe["raw_secret_visible"] if "raw_secret_visible" in safe else True


def test_sandbox_content_requires_exactly_one_owned_source() -> None:
    common = {
        "binding_id": "evaluation.crm.public",
        "dataset_reference": "evaluation-dataset",
        "fixture_profile_reference": "evaluation-fixture",
        "required_record_types": ("crm_customer",),
        "acceptance_criteria_references": ("CRM-CONTEXT-01",),
    }

    with pytest.raises(ValueError, match="exactly one"):
        SandboxContentContract(
            **common,
            customer_owned=True,
            project_owned=True,
        )

    with pytest.raises(ValueError, match="exactly one"):
        SandboxContentContract(
            **common,
            customer_owned=False,
            project_owned=False,
        )


def test_sandbox_reference_requires_exactly_one_scope() -> None:
    common = {
        "binding_id": "evaluation.crm.public",
        "provider_id": "anonymous",
        "secret_reference": "public",
    }
    with pytest.raises(ValueError, match="exactly one"):
        SandboxSecretReference(
            **common,
            customer_scoped=True,
            project_scoped=True,
        )
    with pytest.raises(ValueError, match="exactly one"):
        SandboxSecretReference(
            **common,
            customer_scoped=False,
            project_scoped=False,
        )


def test_customer_owned_sandbox_preserves_legacy_provisioning_fingerprint() -> None:
    binding = {
        "binding_id": "evaluation.crm.customer",
        "task_id": "crm.customer_context",
        "method": "GET",
        "path": "/users/1",
    }
    secret_reference = SandboxSecretReference(
        binding_id="evaluation.crm.customer",
        provider_id="anonymous",
        secret_reference="public",
    )
    content = SandboxContentContract(
        binding_id="evaluation.crm.customer",
        dataset_reference="customer-evaluation-dataset",
        fixture_profile_reference="crm-context-v1",
        required_record_types=("crm_customer",),
        acceptance_criteria_references=("CRM-CONTEXT-01",),
    )

    legacy_content = content.model_dump(mode="json")
    legacy_content.pop("project_owned")
    legacy = {
        "binding": binding,
        "request_mapping": None,
        "secret_reference": {
            "binding_id": secret_reference.binding_id,
            "provider_id": secret_reference.provider_id,
            "secret_reference": secret_reference.secret_reference,
        },
        "content_contract": legacy_content,
    }
    expected = sha256(
        dumps(
            legacy,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            default=str,
        ).encode("utf-8")
    ).hexdigest()

    assert (
        sandbox_provisioning_fingerprint(
            binding=binding,
            request_mapping=None,
            secret_reference=secret_reference,
            content_contract=content,
        )
        == expected
    )


def test_owned_crm_preset_builds_only_read_only_project_sandbox_authority() -> None:
    body = owned_preset.OwnedCrmContextPresetRequest(
        base_url="https://processual-maestro-kernel.onrender.com"
    )
    binding = owned_preset._binding(body)
    content = owned_preset._content(binding.binding_id)
    reference = owned_preset._reference(binding.binding_id)

    assert binding.task_id == "crm.customer_context"
    assert binding.adapter_contract_id == "crm"
    assert binding.method == "GET"
    assert binding.path == "/users/1"
    assert binding.required_scope_ids == ["crm:read"]
    assert binding.field_mapping["customer_id"] == "$.id"
    assert content.customer_owned is False
    assert content.project_owned is True
    assert content.synthetic_or_nonproduction is True
    assert reference.provider_id == "anonymous"
    assert reference.secret_reference == "public"
    assert reference.customer_scoped is False
    assert reference.project_scoped is True
    assert reference.value_included is False


@pytest.mark.asyncio
async def test_owned_crm_preset_reaches_ready_only_after_catalog_selectable(monkeypatch) -> None:
    async def allow(current_user, request):
        del request
        return current_user

    async def fake_provision(*, binding_id, body, request, current_user):
        del request, current_user
        assert binding_id == "evaluation.crm.customer_context.owned"
        assert body.binding.method == "GET"
        assert body.content_contract.project_owned is True
        assert body.secret_reference.project_scoped is True
        return {"persisted": True}

    async def fake_proof(*, binding_id, body, request, current_user):
        del request, current_user
        assert binding_id == "evaluation.crm.customer_context.owned"
        assert body.task_input == {"customer_id": "sandbox-customer-001"}
        return {
            "operational_proof": True,
            "peer_address_verified": True,
            "network_request_executed": True,
            "mapping_valid": True,
            "ready_for_task_consumption": True,
            "evidence_sha256": "e" * 64,
        }

    async def fake_catalog(*, request, current_user):
        del request, current_user
        return {
            "bindings": [
                {
                    "binding_id": "evaluation.crm.customer_context.owned",
                    "task_id": "crm.customer_context",
                    "selectable": True,
                    "sandbox_readiness": {"sandbox_ready": True},
                    "active_sandbox_grant": {"grant_id": "sandbox_grant"},
                }
            ]
        }

    monkeypatch.setattr(owned_preset, "require_active_platform_admin", allow)
    monkeypatch.setattr(owned_preset, "provision_evaluation_binding", fake_provision)
    monkeypatch.setattr(
        owned_preset,
        "execute_evaluation_sandbox_operational_proof",
        fake_proof,
    )
    monkeypatch.setattr(owned_preset, "evaluation_binding_catalog", fake_catalog)

    result = await owned_preset.prepare_owned_crm_context_preset(
        body=owned_preset.OwnedCrmContextPresetRequest(
            base_url="https://processual-maestro-kernel.onrender.com"
        ),
        request=object(),
        current_user={"sub": "admin"},
    )

    assert result["status"] == "ready"
    assert result["preset_id"] == "CRM-CONTEXT-01"
    assert result["binding_selectable"] is True
    assert result["content_owner"] == "project"
    assert result["credential_reference_scope"] == "project"
    assert result["next_grant"]["evaluation_type"] == "crm"
    assert result["next_grant"]["allowed_task_ids"] == ["crm.customer_context"]
    assert result["next_grant"]["allowed_binding_ids"] == [
        "evaluation.crm.customer_context.owned"
    ]
    assert result["next_grant"]["allowed_endpoints"] == [
        {"method": "POST", "path": "/evaluation/runtime/task-execute"}
    ]
    assert result["next_grant"]["quota"] == 100
    assert result["production_allowed"] is False
    assert result["raw_secret_visible"] is False
    assert result["raw_payload_visible"] is False


@pytest.mark.asyncio
async def test_status_enrichment_returns_only_sealed_grant_scenarios(monkeypatch) -> None:
    async def fake_status(current_user):
        return {
            "credential_status": "active",
            "grant_id": "eval_test",
            "api_key_id": "evalkey_test",
            "quota": {"limit": 100, "used": 0, "remaining": 100},
            "production_allowed": False,
        }

    async def fake_load(owner_id: str):
        assert owner_id == "owner-1"
        return {
            "evaluation_grants_v1": [
                {
                    "grant_id": "eval_test",
                    "allowed_task_ids": ["crm.customer_context"],
                    "allowed_binding_ids": ["crm.context.eval"],
                    "allowed_endpoints": [
                        {
                            "method": "POST",
                            "path": "/evaluation/runtime/task-execute",
                        }
                    ],
                }
            ],
            "enterprise_endpoint_bindings_v1": [
                {
                    "binding_id": "crm.context.eval",
                    "task_id": "crm.customer_context",
                },
                {
                    "binding_id": "billing.unrelated",
                    "task_id": "billing.account_context",
                },
            ],
        }

    monkeypatch.setattr(scenarios_runtime, "evaluation_runtime_status", fake_status)
    monkeypatch.setattr(scenarios_runtime, "load_evaluation_authority_state", fake_load)

    payload = await scenarios_runtime.evaluation_runtime_status_with_scenarios(
        {
            "sub": "owner-1",
            "evaluation_grant_id": "eval_test",
            "api_key_id": "evalkey_test",
        }
    )

    assert payload["guided_scenario_count"] == 1
    scenario = payload["guided_scenarios"][0]
    assert scenario["scenario_id"] == "CRM-CONTEXT-01"
    assert scenario["task_id"] == "crm.customer_context"
    assert scenario["binding_ids"] == ["crm.context.eval"]
    assert scenario["runnable"] is True
    assert payload["scenario_catalog_source"] == "sealed_evaluation_grant"
    assert payload["scenario_status_reads_consume_quota"] is False
    assert payload["raw_scenario_input_persisted"] is False
    assert payload["production_allowed"] is False


@pytest.mark.asyncio
async def test_status_enrichment_fails_closed_without_evaluation_identity(monkeypatch) -> None:
    async def fake_status(current_user):
        return {"credential_status": "active"}

    monkeypatch.setattr(scenarios_runtime, "evaluation_runtime_status", fake_status)

    with pytest.raises(Exception) as exc_info:
        await scenarios_runtime.evaluation_runtime_status_with_scenarios({})

    assert getattr(exc_info.value, "status_code", None) == 403
    assert getattr(exc_info.value, "detail", "") == "Governed Evaluation credential required."
