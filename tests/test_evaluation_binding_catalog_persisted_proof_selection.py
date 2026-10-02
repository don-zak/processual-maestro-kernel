from __future__ import annotations

from datetime import UTC, datetime

from processual_api.integrations.enterprise_endpoint_bindings import (
    BINDING_STORAGE_KEY,
    EnterpriseEndpointBindingSpec,
)
from processual_api.integrations.integration_task_catalog import get_integration_task
from processual_api.integrations.sandbox_operational_readiness import (
    SANDBOX_CONTENT_STORAGE_KEY,
    SANDBOX_SECRET_REFERENCE_STORAGE_KEY,
    SandboxContentContract,
    SandboxSecretReference,
    sandbox_provisioning_fingerprint,
)
from processual_api.routers import settings_admin_evaluation_binding_catalog as catalog
from processual_api.routers.settings_enterprise_endpoint_bindings_runtime import (
    SANDBOX_EVIDENCE_STORAGE_KEY,
)


def _ready_raw() -> tuple[dict, EnterpriseEndpointBindingSpec]:
    task = get_integration_task("crm.customer_context")
    spec = EnterpriseEndpointBindingSpec(
        binding_id="evaluation.crm.customer_context.owned",
        display_name="Evaluation CRM customer context",
        adapter_contract_id=task.adapter_contract_id,
        task_id=task.task_id,
        credential_profile_id="enterprise_core_api_reference",
        base_url="https://processual-maestro-evaluation-sandbox.example",
        method="GET",
        path="/crm/customers/1",
        required_scope_ids=list(task.required_scope_ids),
        field_mapping={field: f"$.{field}" for field in task.required_input_fields},
    )
    content = SandboxContentContract(
        binding_id=spec.binding_id,
        dataset_reference="evaluation_crm_dataset_v1",
        fixture_profile_reference="evaluation_crm_fixture_v1",
        required_record_types=("customer",),
        acceptance_criteria_references=("evaluation_crm_contract_v1",),
    )
    secret = SandboxSecretReference(
        binding_id=spec.binding_id,
        provider_id="anonymous_public_sandbox",
        secret_reference="evaluation/public-sandbox",
    )
    provisioning = sandbox_provisioning_fingerprint(
        binding=spec.model_dump(mode="json"),
        request_mapping=None,
        secret_reference=secret,
        content_contract=content,
    )
    raw = {
        BINDING_STORAGE_KEY: [spec.model_dump(mode="json")],
        SANDBOX_CONTENT_STORAGE_KEY: [content.model_dump(mode="json")],
        SANDBOX_SECRET_REFERENCE_STORAGE_KEY: [secret.model_dump(mode="json")],
        SANDBOX_EVIDENCE_STORAGE_KEY: [
            {
                "binding_id": spec.binding_id,
                "task_id": spec.task_id,
                "operational_proof": True,
                "peer_address_verified": True,
                "customer_secret_reference_configured": True,
                "network_request_executed": True,
                "mapping_valid": True,
                "ready_for_task_consumption": True,
                "provisioning_sha256": provisioning,
                "evidence_sha256": "b" * 64,
                "production_allowed": False,
                "runtime_connector_approved": False,
                "completed_at": datetime.now(UTC).isoformat(),
            }
        ],
    }
    return raw, spec


def test_persisted_matching_proof_is_sufficient_for_catalog_selection(monkeypatch) -> None:
    raw, spec = _ready_raw()

    def no_active_grant(*args, **kwargs):
        raise catalog.SandboxGrantError("sandbox_execution_grant_not_found")

    monkeypatch.setattr(catalog, "resolve_active_sandbox_execution_grant", no_active_grant)
    item = catalog._binding_catalog_item(raw, raw[BINDING_STORAGE_KEY][0])

    assert item["binding_id"] == spec.binding_id
    assert item["sandbox_readiness"]["sandbox_ready"] is True
    assert item["active_sandbox_grant"] is None
    assert item["selection_basis"] == "persisted_matching_sandbox_proof"
    assert item["selectable"] is True
    assert item["production_allowed"] is False


def test_catalog_selection_does_not_regress_to_transient_grant_ttl_dependency() -> None:
    source = (
        __import__("pathlib").Path(__file__).resolve().parents[1]
        / "processual_api"
        / "routers"
        / "settings_admin_evaluation_binding_catalog.py"
    ).read_text(encoding="utf-8")

    assert 'selectable = bool(readiness["sandbox_ready"])' in source
    assert 'selection_basis": "persisted_matching_sandbox_proof"' in source
    assert 'readiness["sandbox_ready"] and active_grant is not None' not in source
