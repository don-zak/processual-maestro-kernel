"""Pydantic request/response schemas for all API endpoints."""

from .cgt import CGTEvaluateRequest, CGTEvaluateResponse, FateView
from .external_connectivity import (
    CustomerReferencePackageSubmissionRequest,
    ExternalConnectivityCaseCreateRequest,
    ExternalConnectivityCaseResponse,
    ExternalConnectivityReadinessAssessmentResponse,
)
from .governance import FateReport, GovernanceReport
from .workflows import WorkflowCreateRequest, WorkflowDetailResponse, WorkflowResponse

__all__ = [
    "CGTEvaluateRequest",
    "CGTEvaluateResponse",
    "FateView",
    "WorkflowCreateRequest",
    "WorkflowResponse",
    "WorkflowDetailResponse",
    "GovernanceReport",
    "FateReport",
    "CustomerReferencePackageSubmissionRequest",
    "ExternalConnectivityCaseCreateRequest",
    "ExternalConnectivityCaseResponse",
    "ExternalConnectivityReadinessAssessmentResponse",
]
