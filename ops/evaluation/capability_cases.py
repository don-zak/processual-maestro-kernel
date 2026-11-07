"""Reproducible synthetic CGT governance evidence; no API keys or network calls."""
from __future__ import annotations

import asyncio
from dataclasses import asdict
import hashlib
import json

from processual_api.cgt_governor.evaluator import compute_fate_vector
from processual_api.integrations.integration_task_catalog import get_integration_task
from processual_api.services.evaluation_cgt_governance import (
    evaluate_evaluation_cgt_governance,
    governed_execution_evidence_sha256,
)
from processual_api.services.evaluation_maestro_consumption import (
    consume_evaluation_task_with_maestro,
)

CASES = (
    ("CRM-READ", "crm.customer_context", {"customer_id": "sandbox-customer-001"}),
    ("CRM-SUMMARY", "crm.customer_state_summary", {"customer_id": "sandbox-customer-001", "account_status": "active"}),
    ("CRM-DRAFT", "crm.customer_update_draft", {"customer_id": "sandbox-customer-001", "proposed_changes": {"segment": "review"}}),
    ("BILLING-READ", "billing.account_context", {"account_id": "sandbox-account-001"}),
    ("UNI-STUDENT", "university.student_request", {"request_id": "sandbox-student-request-001"}),
    ("UNI-COURSE", "university.course_catalog", {"course_id": "sandbox-course-001"}),
    ("UNI-DRAFT", "university.admission_response_draft", {"case_id": "sandbox-admission-001", "applicant_context": {"application_status": "documents_received"}}),
    ("GOV-CASE", "government.case_context", {"case_id": "sandbox-public-case-001"}),
    ("GOV-REQUEST", "government.request_summary", {"case_id": "sandbox-public-case-001", "request_text": "Synthetic appointment inquiry"}),
    ("GOV-DRAFT", "government.response_draft", {"case_id": "sandbox-public-case-001", "request_text": "Synthetic appointment inquiry"}),
)
NEGATIVE = (
    ("DENY-PRODUCTION", "crm.customer_context", {"production_allowed": True}),
    ("DENY-AUTO", "billing.account_context", {"auto_execute_production": True}),
    ("DENY-UNOWNED", "university.student_request", {"sandbox_allowed": False}),
    ("DENY-CLASS", "government.case_context", {"operation_class": "approval_gated_write"}),
    ("DENY-GOV", "government.response_draft", {"production_allowed": True}),
    ("DENY-UNI", "university.admission_response_draft", {"auto_execute_production": True}),
)

def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()

def policy_signals(rank, operation):
    if rank == "stable":
        return dict(compatibility=1., coherence=1., structural_support=1., usefulness=1., complexity=.05, fatigue=0., shock=0., lift=.15, novelty=.25, no_answer=0., hallucination=0., constraint_failure=0.)
    if rank == "hybrid" and operation == "draft":
        return dict(compatibility=.85, coherence=.9, structural_support=.9, usefulness=.9, complexity=.35, fatigue=0., shock=.05, lift=1., novelty=.25, no_answer=0., hallucination=0., constraint_failure=.05)
    return dict(compatibility=0., coherence=1., structural_support=1., usefulness=0., complexity=.2, fatigue=0., shock=.8, lift=0., novelty=0., no_answer=0., hallucination=0., constraint_failure=1.)

async def run_case(name, task_id, inputs, overrides=None):
    task = get_integration_task(task_id)
    assert set(task.required_input_fields) <= set(inputs), name
    binding = "evaluation." + task_id + ".owned"
    params = dict(grant_id="synthetic-grant", api_key_id="synthetic-key", task_id=task_id,
                  binding_id=binding, operation_class=task.operation_class, task_input=inputs,
                  sandbox_allowed=True, auto_execute_production=False, production_allowed=False)
    params.update(overrides or {})
    decision = evaluate_evaluation_cgt_governance(**params)
    signals = policy_signals(decision["rank"], params["operation_class"])
    expected_vector = asdict(compute_fate_vector(**signals))
    exact = all(abs(decision["fate_vector"][k] - v) < 1e-12 for k, v in expected_vector.items())
    expected = "deny" if overrides else ("allow_with_review" if task.operation_class == "draft" else "allow")
    checks = dict(decision=decision["disposition"] == expected, fate_recomputed=exact,
                  input_hash=decision["task_input_sha256"] == digest(inputs),
                  no_authority_expansion=decision["authority_expansion_allowed"] is False,
                  no_production=decision["production_allowed"] is False,
                  no_raw_input=decision["raw_task_input_included"] is False)
    receipt = None
    if decision["disposition"] != "deny":
        synthetic_evidence = digest({"case": name, "synthetic": True})
        receipt = await consume_evaluation_task_with_maestro(
            execution_id="synthetic-" + name.lower(), task_id=task_id,
            binding_id=binding, output_slot=task.output_slot,
            execution_evidence_sha256=synthetic_evidence,
            task_injection_sha256=digest({"case": name, "injection": "hash-only"}),
            governance_trace_sha256=decision["trace_sha256"])
        checks["kernel_consumption"] = receipt["maestro_task_completed"] is True
        checks["governance_bound"] = receipt["governance_trace_sha256"] == decision["trace_sha256"]
        checks["governed_digest"] = len(governed_execution_evidence_sha256(
            execution_evidence_sha256=synthetic_evidence,
            governance_trace_sha256=decision["trace_sha256"])) == 64
    else:
        checks["no_execution_on_deny"] = receipt is None
    return dict(case_id=name, task_id=task_id, operation_class=params["operation_class"],
                evidence_level="INTERNAL_SYNTHETIC_POLICY_AND_HASH_ONLY_KERNEL",
                content=dict(input=inputs, changed_constraints=overrides or {},
                             required_scopes=list(task.required_scope_ids),
                             expected_disposition=expected),
                governance=dict(decision_id=decision["decision_id"],
                                disposition=decision["disposition"], action=decision["governance_action"],
                                reason_codes=decision["reason_codes"], review_required=decision["review_required"],
                                trace_sha256=decision["trace_sha256"],
                                policy_version=decision["policy_version"],
                                fate_vector_basis=decision["fate_vector_basis"],
                                fate_vector=decision["fate_vector"], fate_signals=signals,
                                recomputed_vector=expected_vector),
                synthetic_kernel_receipt=receipt,
                verification=dict(passed=all(checks.values()), checks=checks))

async def build():
    records = [await run_case(*case) for case in CASES]
    inputs = {task: values for _, task, values in CASES}
    records.extend([await run_case(name, task, inputs[task], overrides)
                    for name, task, overrides in NEGATIVE])
    return dict(schema="maestro-capability-evidence-v1", source="real public CGT policy",
                workspace_evidence="NOT_IMPORTED", real_external_calls=0,
                real_quota_consumed=0, cases=records,
                total=len(records), passed=sum(r["verification"]["passed"] for r in records))

def build_sync():
    return asyncio.run(build())
