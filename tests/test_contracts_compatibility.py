from __future__ import annotations

import pickle

import processual_kernel
from processual_kernel import contracts
from processual_kernel import types as legacy_types


ENUM_CONTRACT_NAMES = (
    "AgentState",
    "AgentCriticality",
    "WorkflowState",
    "StepState",
    "MaestroAction",
)


def test_enum_contracts_keep_legacy_and_public_object_identity() -> None:
    for name in ENUM_CONTRACT_NAMES:
        contract = getattr(contracts, name)
        assert getattr(legacy_types, name) is contract
        assert getattr(processual_kernel, name) is contract


def test_enum_contracts_keep_legacy_serialization_identity() -> None:
    for name in ENUM_CONTRACT_NAMES:
        contract = getattr(contracts, name)
        assert contract.__module__ == "processual_kernel.types"
        member = next(iter(contract))
        assert pickle.loads(pickle.dumps(member)) is member


def test_enum_contract_values_are_unchanged() -> None:
    assert legacy_types.AgentState.ACTIVE == "active"
    assert legacy_types.AgentCriticality.CRITICAL == "critical"
    assert legacy_types.WorkflowState.ESCALATED == "escalated"
    assert legacy_types.StepState.SKIPPED == "skipped"
    assert legacy_types.MaestroAction.FINALIZE == "finalize"
