"""Declarative credential readiness profiles for enterprise integrations.

This module does not store secrets, open sockets, call external APIs, or
approve runtime connectors. It defines the customer-side readiness contract
that must exist before any real adapter can be considered for sandbox or
production integration.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

AuthMethod = Literal[
    "api_key_reference",
    "oauth_client_reference",
    "mtls_certificate_reference",
    "signed_webhook_reference",
    "customer_vault_reference",
]

ReadinessStatus = Literal[
    "draft_review",
    "blocked_pending_customer_inputs",
    "not_runtime_approved",
]


COMMON_FORBIDDEN_SECRET_MATERIAL = (
    "raw API key values",
    "raw OAuth client secrets",
    "raw passwords",
    "raw access tokens",
    "raw refresh tokens",
    "private key material",
    "certificate private keys",
    "webhook signing secret values",
    "database connection strings",
)

COMMON_REQUIRED_CUSTOMER_INPUTS = (
    "api_documentation",
    "sandbox_access",
    "test_credentials_policy",
    "scope_matrix",
    "technical_contact",
    "acceptance_criteria",
    "security_requirements",
    "credential_owner",
    "rotation_policy",
    "customer_endpoint_inventory",
)

COMMON_REQUIRED_SECURITY_CONTROLS = (
    "enterprise_review",
    "security_review",
    "sandbox_before_production",
    "least_privilege_scopes",
    "supervisor_approval_for_production_credentials",
    "no_raw_secrets_in_support_notes",
    "customer_vault_or_reference_storage",
    "audit_logging_required",
)


@dataclass(frozen=True)
class CredentialProfile:
    """Declarative credential readiness profile.

    The profile describes what must be provided and reviewed. It is not a
    credential store and it does not make runtime connections.
    """

    credential_profile_id: str
    display_name: str
    description: str
    adapter_contract_ids: tuple[str, ...]
    supported_auth_methods: tuple[AuthMethod, ...]
    forbidden_secret_material: tuple[str, ...]
    required_customer_inputs: tuple[str, ...]
    required_security_controls: tuple[str, ...]
    rotation_policy_required: bool
    sandbox_required: bool
    production_credential_approval_required: bool
    technical_contact_required: bool
    security_review_required: bool
    customer_endpoint_inventory_required: bool
    readiness_status: ReadinessStatus
    approved_for_runtime: bool

    @property
    def runtime_connector_approved(self) -> bool:
        """Mirror adapter-contract posture for readiness screens."""

        return self.approved_for_runtime


def _iter_adapter_contracts() -> tuple[object, ...]:
    """Load adapter contracts without assuming a specific registry shape."""

    try:
        from . import adapter_contracts as contracts_module
    except ImportError:
        return ()

    list_contracts = getattr(contracts_module, "list_adapter_contracts", None)
    if callable(list_contracts):
        return tuple(list_contracts())

    registry = getattr(contracts_module, "ADAPTER_CONTRACTS", ())
    if isinstance(registry, dict):
        return tuple(registry.values())

    return tuple(registry)


def _known_adapter_contract_ids() -> frozenset[str]:
    contract_ids: set[str] = set()
    for contract in _iter_adapter_contracts():
        contract_id = getattr(contract, "contract_id", None)
        if contract_id:
            contract_ids.add(str(contract_id))
    return frozenset(contract_ids)


def _contract_haystack(contract: object) -> str:
    parts: list[str] = []

    for attribute in ("contract_id", "display_name", "description"):
        value = getattr(contract, attribute, "")
        if value:
            parts.append(str(value))

    for attribute in ("domains", "sectors"):
        values = getattr(contract, attribute, ())
        parts.extend(str(value) for value in values)

    return " ".join(parts).lower()


def _contract_id_for(primary_hint: str, *extra_hints: str) -> str:
    """Return an existing adapter contract id when the hint can be resolved."""

    hints = (primary_hint, *extra_hints)
    normalized_hints = tuple(hint.replace("_", " ").lower() for hint in hints)

    for contract in _iter_adapter_contracts():
        contract_id = str(getattr(contract, "contract_id", ""))
        haystack = _contract_haystack(contract).replace("_", " ").replace("_", " ")

        if any(hint in haystack for hint in normalized_hints):
            return contract_id

    return primary_hint


CRM_CONTRACT_ID = _contract_id_for("crm", "customer relationship")
BILLING_CONTRACT_ID = _contract_id_for("billing")
TICKETING_CONTRACT_ID = _contract_id_for("ticketing", "support ticket")
ORDER_CONTRACT_ID = _contract_id_for("order_management", "order management")
NETWORK_CONTRACT_ID = _contract_id_for("network_assurance", "network assurance")
DOCUMENT_CONTRACT_ID = _contract_id_for("document", "document repository")
BANKING_KYC_CONTRACT_ID = _contract_id_for("banking_kyc", "kyc")
GOVERNMENT_CASE_CONTRACT_ID = "government_case"
RESEARCH_DATASET_CONTRACT_ID = _contract_id_for("research_dataset", "dataset")
UNIVERSITY_STUDENT_CONTRACT_ID = _contract_id_for("university_student", "student")
HELPDESK_CONTRACT_ID = "enterprise_helpdesk"


CREDENTIAL_PROFILES: tuple[CredentialProfile, ...] = (
    CredentialProfile(
        credential_profile_id="enterprise_core_api_reference",
        display_name="Enterprise Core API Reference",
        description=(
            "Readiness profile for customer-owned CRM, billing, ticketing, "
            "order management, and helpdesk API references."
        ),
        adapter_contract_ids=(
            CRM_CONTRACT_ID,
            BILLING_CONTRACT_ID,
            TICKETING_CONTRACT_ID,
            ORDER_CONTRACT_ID,
            HELPDESK_CONTRACT_ID,
        ),
        supported_auth_methods=(
            "api_key_reference",
            "oauth_client_reference",
            "customer_vault_reference",
        ),
        forbidden_secret_material=COMMON_FORBIDDEN_SECRET_MATERIAL,
        required_customer_inputs=COMMON_REQUIRED_CUSTOMER_INPUTS,
        required_security_controls=COMMON_REQUIRED_SECURITY_CONTROLS,
        rotation_policy_required=True,
        sandbox_required=True,
        production_credential_approval_required=True,
        technical_contact_required=True,
        security_review_required=True,
        customer_endpoint_inventory_required=True,
        readiness_status="blocked_pending_customer_inputs",
        approved_for_runtime=False,
    ),
    CredentialProfile(
        credential_profile_id="telecom_operations_api_reference",
        display_name="Telecom Operations API Reference",
        description=(
            "Readiness profile for telecom CRM, billing, ticketing, order, "
            "and network assurance API references."
        ),
        adapter_contract_ids=(
            CRM_CONTRACT_ID,
            BILLING_CONTRACT_ID,
            TICKETING_CONTRACT_ID,
            ORDER_CONTRACT_ID,
            NETWORK_CONTRACT_ID,
        ),
        supported_auth_methods=(
            "api_key_reference",
            "oauth_client_reference",
            "mtls_certificate_reference",
            "customer_vault_reference",
        ),
        forbidden_secret_material=COMMON_FORBIDDEN_SECRET_MATERIAL,
        required_customer_inputs=COMMON_REQUIRED_CUSTOMER_INPUTS,
        required_security_controls=COMMON_REQUIRED_SECURITY_CONTROLS,
        rotation_policy_required=True,
        sandbox_required=True,
        production_credential_approval_required=True,
        technical_contact_required=True,
        security_review_required=True,
        customer_endpoint_inventory_required=True,
        readiness_status="blocked_pending_customer_inputs",
        approved_for_runtime=False,
    ),
    CredentialProfile(
        credential_profile_id="document_repository_reference",
        display_name="Document Repository Reference",
        description=(
            "Readiness profile for document systems where Maestro may read "
            "or route customer-approved document metadata."
        ),
        adapter_contract_ids=(DOCUMENT_CONTRACT_ID,),
        supported_auth_methods=(
            "api_key_reference",
            "oauth_client_reference",
            "signed_webhook_reference",
            "customer_vault_reference",
        ),
        forbidden_secret_material=COMMON_FORBIDDEN_SECRET_MATERIAL,
        required_customer_inputs=COMMON_REQUIRED_CUSTOMER_INPUTS,
        required_security_controls=COMMON_REQUIRED_SECURITY_CONTROLS,
        rotation_policy_required=True,
        sandbox_required=True,
        production_credential_approval_required=True,
        technical_contact_required=True,
        security_review_required=True,
        customer_endpoint_inventory_required=True,
        readiness_status="blocked_pending_customer_inputs",
        approved_for_runtime=False,
    ),
    CredentialProfile(
        credential_profile_id="banking_kyc_api_reference",
        display_name="Banking KYC API Reference",
        description=(
            "Readiness profile for banking KYC adapter planning. It remains "
            "blocked until security, legal, and sandbox review are complete."
        ),
        adapter_contract_ids=(BANKING_KYC_CONTRACT_ID, DOCUMENT_CONTRACT_ID),
        supported_auth_methods=(
            "oauth_client_reference",
            "mtls_certificate_reference",
            "customer_vault_reference",
        ),
        forbidden_secret_material=COMMON_FORBIDDEN_SECRET_MATERIAL,
        required_customer_inputs=COMMON_REQUIRED_CUSTOMER_INPUTS,
        required_security_controls=COMMON_REQUIRED_SECURITY_CONTROLS,
        rotation_policy_required=True,
        sandbox_required=True,
        production_credential_approval_required=True,
        technical_contact_required=True,
        security_review_required=True,
        customer_endpoint_inventory_required=True,
        readiness_status="blocked_pending_customer_inputs",
        approved_for_runtime=False,
    ),
    CredentialProfile(
        credential_profile_id="government_case_api_reference",
        display_name="Government Case API Reference",
        description=(
            "Readiness profile for government case-management integration "
            "planning under strict customer approval and audit requirements."
        ),
        adapter_contract_ids=(
            GOVERNMENT_CASE_CONTRACT_ID,
            DOCUMENT_CONTRACT_ID,
        ),
        supported_auth_methods=(
            "oauth_client_reference",
            "mtls_certificate_reference",
            "signed_webhook_reference",
            "customer_vault_reference",
        ),
        forbidden_secret_material=COMMON_FORBIDDEN_SECRET_MATERIAL,
        required_customer_inputs=COMMON_REQUIRED_CUSTOMER_INPUTS,
        required_security_controls=COMMON_REQUIRED_SECURITY_CONTROLS,
        rotation_policy_required=True,
        sandbox_required=True,
        production_credential_approval_required=True,
        technical_contact_required=True,
        security_review_required=True,
        customer_endpoint_inventory_required=True,
        readiness_status="blocked_pending_customer_inputs",
        approved_for_runtime=False,
    ),
    CredentialProfile(
        credential_profile_id="research_dataset_api_reference",
        display_name="Research Dataset API Reference",
        description=(
            "Readiness profile for research dataset access where customer "
            "approval, data classification, and sandbox review are required."
        ),
        adapter_contract_ids=(
            RESEARCH_DATASET_CONTRACT_ID,
            DOCUMENT_CONTRACT_ID,
        ),
        supported_auth_methods=(
            "api_key_reference",
            "oauth_client_reference",
            "customer_vault_reference",
        ),
        forbidden_secret_material=COMMON_FORBIDDEN_SECRET_MATERIAL,
        required_customer_inputs=COMMON_REQUIRED_CUSTOMER_INPUTS,
        required_security_controls=COMMON_REQUIRED_SECURITY_CONTROLS,
        rotation_policy_required=True,
        sandbox_required=True,
        production_credential_approval_required=True,
        technical_contact_required=True,
        security_review_required=True,
        customer_endpoint_inventory_required=True,
        readiness_status="blocked_pending_customer_inputs",
        approved_for_runtime=False,
    ),
    CredentialProfile(
        credential_profile_id="university_student_api_reference",
        display_name="University Student API Reference",
        description=(
            "Readiness profile for university student-information integration "
            "planning with least-privilege and sandbox-first controls."
        ),
        adapter_contract_ids=(UNIVERSITY_STUDENT_CONTRACT_ID,),
        supported_auth_methods=(
            "api_key_reference",
            "oauth_client_reference",
            "customer_vault_reference",
        ),
        forbidden_secret_material=COMMON_FORBIDDEN_SECRET_MATERIAL,
        required_customer_inputs=COMMON_REQUIRED_CUSTOMER_INPUTS,
        required_security_controls=COMMON_REQUIRED_SECURITY_CONTROLS,
        rotation_policy_required=True,
        sandbox_required=True,
        production_credential_approval_required=True,
        technical_contact_required=True,
        security_review_required=True,
        customer_endpoint_inventory_required=True,
        readiness_status="blocked_pending_customer_inputs",
        approved_for_runtime=False,
    ),
)


def list_credential_profiles() -> tuple[CredentialProfile, ...]:
    """Return all declarative credential readiness profiles."""

    return CREDENTIAL_PROFILES


def get_credential_profile(credential_profile_id: str) -> CredentialProfile:
    """Return a credential readiness profile by id."""

    for profile in CREDENTIAL_PROFILES:
        if profile.credential_profile_id == credential_profile_id:
            return profile

    raise KeyError(f"Unknown credential profile: {credential_profile_id}")


def validate_credential_profiles() -> tuple[str, ...]:
    """Validate profile invariants without making runtime connections."""

    issues: list[str] = []
    profile_ids: set[str] = set()
    adapter_contract_ids = _known_adapter_contract_ids()

    for profile in CREDENTIAL_PROFILES:
        if profile.credential_profile_id in profile_ids:
            issues.append(f"duplicate profile id: {profile.credential_profile_id}")
        profile_ids.add(profile.credential_profile_id)

        if not profile.adapter_contract_ids:
            issues.append(f"{profile.credential_profile_id}: missing contracts")

        if profile.approved_for_runtime:
            issues.append(f"{profile.credential_profile_id}: runtime approved")

        if profile.runtime_connector_approved:
            issues.append(f"{profile.credential_profile_id}: connector approved")

        if not profile.sandbox_required:
            issues.append(f"{profile.credential_profile_id}: sandbox not required")

        if not profile.security_review_required:
            issues.append(f"{profile.credential_profile_id}: review not required")

        if not profile.technical_contact_required:
            issues.append(f"{profile.credential_profile_id}: contact not required")

        if not profile.rotation_policy_required:
            issues.append(f"{profile.credential_profile_id}: rotation not required")

        if not profile.production_credential_approval_required:
            issues.append(f"{profile.credential_profile_id}: approval not required")

        if not profile.customer_endpoint_inventory_required:
            issues.append(f"{profile.credential_profile_id}: inventory not required")

        for auth_method in profile.supported_auth_methods:
            if not auth_method.endswith("_reference"):
                issues.append(
                    f"{profile.credential_profile_id}: non-reference auth method"
                )

        if adapter_contract_ids:
            for contract_id in profile.adapter_contract_ids:
                if contract_id not in adapter_contract_ids:
                    issues.append(
                        f"{profile.credential_profile_id}: unknown contract "
                        f"{contract_id}"
                    )

    return tuple(issues)


__all__ = [
    "AuthMethod",
    "CREDENTIAL_PROFILES",
    "COMMON_FORBIDDEN_SECRET_MATERIAL",
    "COMMON_REQUIRED_CUSTOMER_INPUTS",
    "COMMON_REQUIRED_SECURITY_CONTROLS",
    "CredentialProfile",
    "ReadinessStatus",
    "get_credential_profile",
    "list_credential_profiles",
    "validate_credential_profiles",
]
