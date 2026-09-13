from __future__ import annotations

import asyncio

from processual_api.services.evaluation_cgt_governance import (
    evaluate_evaluation_cgt_governance,
    maestro_governed_evidence_sha256,
)
from processual_api.services.evaluation_maestro_consumption import (
    MAESTRO_CONSUMPTION_SCHEMA_VERSION,
    consume_evaluation_task_with_maestro,
)


def _governance(operation_class: str = "draft") -> dict:
    return evaluate_evaluation_cgt_governance(
        grant_id="eval_test",
        api_key_id="evalkey_test",
        task_id="crm.customer_update_draft",
        binding_id="evaluation.crm.customer_update_draft.owned",
        operation_class=operation_class,
        task_input={"customer_id": "sandbox-customer-001"},
        sandbox_allowed=True,
        auto_execute_production=False,
        production_allowed=False,
    )


def test_external_evaluation_governance_exposes_full_fate_vector() -> None:
    governance = _governance()
    assert governance["disposition"] == "allow_with_review"
    assert governance["rank"] == "hybrid"
    assert governance["fate_vector_basis"] == "external-evaluation-policy-signal-profile-v1"
    assert set(governance["fate_vector"]) == {
        "stability",
        "hybridity",
        "distortion",
        "extinction",
        "collapse",
        "flourishing",
        "transient",
    }
    assert all(0.0 <= float(value) <= 1.0 for value in governance["fate_vector"].values())


def test_maestro_consumes_safe_governed_task_outcome() -> None:
    governance = _governance()
    receipt = asyncio.run(
        consume_evaluation_task_with_maestro(
            execution_id="exec_test",
            task_id="crm.customer_update_draft",
            binding_id="evaluation.crm.customer_update_draft.owned",
            output_slot="crm_update_draft",
            execution_evidence_sha256="e" * 64,
            task_injection_sha256="i" * 64,
            governance_trace_sha256=governance["trace_sha256"],
            response_sha256="r" * 64,
        )
    )

    assert receipt["schema_version"] == MAESTRO_CONSUMPTION_SCHEMA_VERSION
    assert receipt["maestro_kernel"] == "ProcessualMaestroKernel"
    assert receipt["maestro_task_completed"] is True
    assert receipt["workflow_state"] == "completed"
    assert receipt["step_state"] == "completed"
    assert receipt["consumption_sha256"]
    assert receipt["receipt_sha256"]
    assert receipt["raw_task_input_included"] is False
    assert receipt["raw_provider_response_included"] is False
    assert receipt["raw_secret_visible"] is False
    assert receipt["production_allowed"] is False

    final = maestro_governed_evidence_sha256(
        governed_execution_evidence_sha256="g" * 64,
        maestro_consumption_sha256=receipt["receipt_sha256"],
    )
    assert len(final) == 64


def test_deny_fate_vector_is_extinction_weighted() -> None:
    governance = evaluate_evaluation_cgt_governance(
        grant_id="eval_test",
        api_key_id="evalkey_test",
        task_id="qualification.cgt.production_mutation_probe",
        binding_id="evaluation.governance.deny_probe",
        operation_class="mutation",
        task_input={"probe_id": "CGT-DENY-01"},
        sandbox_allowed=False,
        auto_execute_production=True,
        production_allowed=True,
    )
    assert governance["disposition"] == "deny"
    assert governance["rank"] == "extinct"
    assert governance["fate_vector"]["extinction"] > governance["fate_vector"]["stability"]
