from __future__ import annotations

from processual_api.integrations.adapter_contracts import list_adapter_contracts
from processual_api.integrations.integration_task_catalog import (
    APPROVAL_GATED_WRITE,
    INTEGRATION_TASK_CATALOG,
    list_integration_tasks,
    list_tasks_for_contract,
    task_catalog_payload,
)
from processual_api.integrations.scope_catalog import get_integration_scope


def test_every_declared_safe_operation_has_exact_task_coverage() -> None:
    for contract in list_adapter_contracts():
        tasks = list_tasks_for_contract(contract.contract_id)
        assert tasks, contract.contract_id
        covered = {task.safe_operation for task in tasks}
        assert covered == set(contract.safe_operations), {
            "contract_id": contract.contract_id,
            "missing": sorted(set(contract.safe_operations) - covered),
            "extra": sorted(covered - set(contract.safe_operations)),
        }


def test_every_required_adapter_scope_is_backed_by_a_task() -> None:
    for contract in list_adapter_contracts():
        covered_scopes = {
            scope_id
            for task in list_tasks_for_contract(contract.contract_id)
            for scope_id in task.required_scope_ids
        }
        assert set(contract.required_scopes) <= covered_scopes, {
            "contract_id": contract.contract_id,
            "missing_required_scopes": sorted(
                set(contract.required_scopes) - covered_scopes
            ),
        }


def test_tasks_never_escape_adapter_scope_contracts() -> None:
    contracts = {
        contract.contract_id: contract for contract in list_adapter_contracts()
    }
    for task in list_integration_tasks():
        contract = contracts[task.adapter_contract_id]
        assert set(task.required_scope_ids) <= set(contract.all_scopes)
        assert task.safe_operation in contract.safe_operations
        assert task.required_input_fields
        assert task.output_slot
        assert task.sandbox_allowed is True
        assert task.production_requires_approval is True
        assert task.auto_execute_production is False


def test_prohibited_operations_are_not_executable_task_operations() -> None:
    safe_task_operations = {
        task.safe_operation.lower() for task in list_integration_tasks()
    }
    for contract in list_adapter_contracts():
        for prohibited in contract.prohibited_operations:
            assert prohibited.lower() not in safe_task_operations


def test_approval_gated_tasks_only_use_supervisor_approval_scopes() -> None:
    for task in list_integration_tasks():
        if task.operation_class != APPROVAL_GATED_WRITE:
            continue
        assert task.required_scope_ids
        assert all(
            get_integration_scope(scope_id).requires_supervisor_approval
            for scope_id in task.required_scope_ids
        )


def test_task_catalog_payload_is_fail_closed_for_production() -> None:
    payload = task_catalog_payload()
    assert payload["task_count"] == len(INTEGRATION_TASK_CATALOG) == 33
    assert payload["production_allowed"] is False
    assert payload["runtime_connector_approved"] is False
    assert len(payload["tasks"]) == 33
    assert all(task["sandbox_allowed"] is True for task in payload["tasks"])
    assert all(task["auto_execute_production"] is False for task in payload["tasks"])


def test_all_current_claimed_domains_have_task_families() -> None:
    contract_ids = {contract.contract_id for contract in list_adapter_contracts()}
    assert contract_ids == {
        "crm",
        "billing",
        "ticketing",
        "order_management",
        "network_assurance",
        "document",
        "banking_kyc",
        "government_case",
        "research_dataset",
        "university_student",
        "enterprise_helpdesk",
    }
    assert {task.adapter_contract_id for task in list_integration_tasks()} == contract_ids
