from __future__ import annotations

import asyncio

import processual_kernel.cgt_bridge as cgt_bridge

from processual_api.services.evaluation_maestro_consumption import (
    MAESTRO_CONSUMPTION_SCHEMA_VERSION,
    MAESTRO_GOVERNANCE_SOURCE,
    consume_evaluation_task_with_maestro,
)


def test_evaluation_maestro_consumption_does_not_require_private_cgt_engine(monkeypatch) -> None:
    """Public External Evaluation must reconcile after CGT pre-admission governance.

    The public build intentionally exposes cgtlib's fallback for private structural
    transition evaluation. Maestro consumption must therefore not invoke a second
    private CGT pass after the authoritative External Evaluation CGT decision has
    already been made before admission.
    """

    def private_engine_must_not_run(*args, **kwargs):
        raise AssertionError("private CGT structural engine must not be called")

    monkeypatch.setattr(
        cgt_bridge,
        "evaluate_structural_transition",
        private_engine_must_not_run,
    )

    receipt = asyncio.run(
        consume_evaluation_task_with_maestro(
            execution_id="exec_reconcile_test",
            task_id="crm.customer_update_draft",
            binding_id="evaluation.crm.customer_update_draft.owned",
            output_slot="crm_update_draft",
            execution_evidence_sha256="e" * 64,
            task_injection_sha256="i" * 64,
            governance_trace_sha256="g" * 64,
            response_sha256="r" * 64,
        )
    )

    assert receipt["schema_version"] == MAESTRO_CONSUMPTION_SCHEMA_VERSION
    assert receipt["schema_version"] == "external-evaluation-maestro-consumption-v2"
    assert receipt["governance_source"] == MAESTRO_GOVERNANCE_SOURCE
    assert receipt["governance_source"] == "external_evaluation_cgt_prevalidated"
    assert receipt["private_cgt_re_evaluation_required"] is False
    assert receipt["maestro_kernel"] == "ProcessualMaestroKernel"
    assert receipt["workflow_state"] == "completed"
    assert receipt["step_state"] == "completed"
    assert receipt["maestro_task_completed"] is True
    assert receipt["consumption_sha256"]
    assert receipt["receipt_sha256"]
    assert receipt["raw_task_input_included"] is False
    assert receipt["raw_provider_response_included"] is False
    assert receipt["raw_secret_visible"] is False
    assert receipt["production_allowed"] is False
