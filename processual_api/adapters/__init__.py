"""Presentation adapters — transform kernel/CGT data for API and frontend display."""

from .agent_runtime import (
    AgentExecutionResult,
    RuntimeAdapter,
    RuntimeAdapterRegistry,
    RuntimeHealth,
    runtime_registry,
)
from .cgt_adapter import arabic_rank_label, recommendation_for_rank
from .frontend_adapter import (
    FateView,
    GovernanceView,
    WorkflowView,
    fate_vector_to_frontend,
    governance_to_frontend,
    workflow_to_frontend,
)
from .kernel_adapter import KernelAdapter

__all__ = [
    "arabic_rank_label",
    "recommendation_for_rank",
    "FateView",
    "WorkflowView",
    "GovernanceView",
    "fate_vector_to_frontend",
    "workflow_to_frontend",
    "governance_to_frontend",
    "KernelAdapter",
    "RuntimeAdapter",
    "RuntimeAdapterRegistry",
    "AgentExecutionResult",
    "RuntimeHealth",
    "runtime_registry",
]
