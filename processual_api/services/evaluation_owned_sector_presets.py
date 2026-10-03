"""Review-only provisioning specifications for six project-owned Evaluation sector fixtures.

This module never provisions anything and cannot authorize production execution.
Only an authenticated platform administrator may use the existing provisioning API.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from processual_api.integrations.enterprise_endpoint_bindings import (
    EnterpriseEndpointBindingSpec, validate_endpoint_binding,
)
from processual_api.integrations.enterprise_endpoint_request_mapping import (
    EnterpriseEndpointRequestMappingSpec, validate_request_mapping,
)
from processual_api.integrations.sandbox_operational_readiness import (
    SandboxContentContract, SandboxSecretReference,
)


@dataclass(frozen=True)
class SectorPreset:
    scenario_id: str
    binding: EnterpriseEndpointBindingSpec
    request_mapping: EnterpriseEndpointRequestMappingSpec | None
    content_contract: SandboxContentContract
    secret_reference: SandboxSecretReference
    sample_input: dict[str, Any]


# (scenario, task, adapter, credential profile, method, path,
#  required response fields, request body fields, sample input, record type)
_DEFINITIONS: tuple[tuple[Any, ...], ...] = (
    ("UNI-STUDENT-01", "university.student_request", "university_student",
     "university_student_api_reference", "GET",
     "/university/requests/sandbox-student-request-001",
     ("request_id", "student_id", "request_text", "status"), (),
     {"request_id": "sandbox-student-request-001"}, "student_request"),
    ("UNI-COURSE-01", "university.course_catalog", "university_student",
     "university_student_api_reference", "GET",
     "/university/courses/sandbox-course-001",
     ("course_id", "title", "description", "requirements", "schedule"), (),
     {"course_id": "sandbox-course-001"}, "course"),
    ("UNI-ADMISSION-01", "university.admission_response_draft", "university_student",
     "university_student_api_reference", "POST",
     "/university/admissions/sandbox-admission-001/response-draft",
     ("case_id", "applicant_context"), ("case_id", "applicant_context"),
     {"case_id": "sandbox-admission-001",
      "applicant_context": {"application_status": "documents_received"}}, "admission_draft"),
    ("GOV-CASE-01", "government.case_context", "government_case",
     "government_case_api_reference", "GET",
     "/government/cases/sandbox-public-case-001",
     ("case_id", "citizen_id", "status", "history", "audit_records"), (),
     {"case_id": "sandbox-public-case-001"}, "public_service_case"),
    ("GOV-REQUEST-01", "government.request_summary", "government_case",
     "government_case_api_reference", "GET",
     "/government/requests/sandbox-public-case-001",
     ("case_id", "request_text", "citizen_id", "history", "attachments"), (),
     {"case_id": "sandbox-public-case-001",
      "request_text": "Synthetic appointment status inquiry"}, "citizen_request"),
    ("GOV-RESPONSE-01", "government.response_draft", "government_case",
     "government_case_api_reference", "POST",
     "/government/cases/sandbox-public-case-001/response-draft",
     ("case_id", "request_text"), ("case_id", "request_text"),
     {"case_id": "sandbox-public-case-001",
      "request_text": "Synthetic appointment status inquiry"}, "response_draft"),
)


def sector_presets(base_url: str) -> tuple[SectorPreset, ...]:
    """Validate reproducible sandbox-only binding contracts without side effects."""
    output: list[SectorPreset] = []
    for scenario, task_id, adapter, profile, method, path, fields, body_fields, sample, record_type in _DEFINITIONS:
        binding_id = "evaluation." + task_id + ".owned"
        from processual_api.integrations.integration_task_catalog import get_integration_task
        task = get_integration_task(task_id)
        binding = EnterpriseEndpointBindingSpec(
            binding_id=binding_id,
            display_name="Project-owned " + scenario + " synthetic sandbox proof",
            adapter_contract_id=adapter,
            task_id=task_id,
            credential_profile_id=profile,
            environment="sandbox",
            base_url=base_url,
            method=method,
            path=path,
            required_scope_ids=list(task.required_scope_ids),
            response_format="json",
            response_data_path="$",
            field_mapping={field: "$." + field for field in fields},
            success_codes=[200],
            timeout_seconds=15,
        )
        validate_endpoint_binding(binding)
        mapping = (
            EnterpriseEndpointRequestMappingSpec(
                binding_id=binding_id,
                body_mapping={field: "$task." + field for field in body_fields},
            )
            if body_fields else None
        )
        if mapping is not None:
            validate_request_mapping(binding, mapping)
        content = SandboxContentContract(
            binding_id=binding_id,
            dataset_reference="project-evaluation-sandbox-sector-v1",
            fixture_profile_reference=scenario.lower() + "-synthetic-v1",
            required_record_types=(record_type,),
            acceptance_criteria_references=(scenario,),
            customer_owned=False,
            project_owned=True,
            synthetic_or_nonproduction=True,
            secrets_included=False,
            raw_payloads_included=False,
        )
        secret = SandboxSecretReference(
            binding_id=binding_id,
            provider_id="anonymous",
            secret_reference="public",
            customer_scoped=False,
            project_scoped=True,
            value_included=False,
        )
        output.append(SectorPreset(scenario, binding, mapping, content, secret, sample))
    return tuple(output)


__all__ = ["SectorPreset", "sector_presets"]
