"""Declarative client-visible operational profiles for integration API keys.

Catalog only:
- no key issuing
- no raw secrets
- no external HTTP
- no runtime connector
- no production connector approval
"""

from copy import deepcopy

API_KEY_OPERATIONAL_PROFILES: tuple[dict[str, object], ...] = (
    {
        "profile_id": "external_partner_access",
        "display_name": "External Partner Access",
        "base_key_profile": "external_partner",
        "client_visible": True,
        "environment": "sandbox",
        "allowed_scopes": (
            "workflow_status:read",
            "usage_summary:read",
            "integration_request:read",
        ),
        "forbidden_scopes": (
            "billing:update",
            "payment:execute",
            "production_write",
            "connector_runtime:execute",
        ),
        "read_only": True,
        "write_allowed": False,
        "restricted_allowed": False,
        "requires_enterprise_plan": True,
        "requires_integration_readiness": True,
        "requires_supervisor_for_write": True,
        "production_allowed": False,
        "runtime_connector_approved": False,
        "next_action": "Request supervisor review for partner API provisioning.",
    },
    {
        "profile_id": "service_integration_read_only",
        "display_name": "Service Integration - Read Only",
        "base_key_profile": "service_integration",
        "client_visible": True,
        "environment": "sandbox",
        "allowed_scopes": (
            "workflow_status:read",
            "usage_summary:read",
            "client_request:read",
        ),
        "forbidden_scopes": (
            "ticket:update",
            "billing:update",
            "kyc_status:finalize",
            "production_write",
        ),
        "read_only": True,
        "write_allowed": False,
        "restricted_allowed": False,
        "requires_enterprise_plan": True,
        "requires_integration_readiness": True,
        "requires_supervisor_for_write": True,
        "production_allowed": False,
        "runtime_connector_approved": False,
        "next_action": "Complete integration readiness before any write scope.",
    },
    {
        "profile_id": "service_integration_support_ticketing",
        "display_name": "Service Integration - Support Ticketing",
        "base_key_profile": "service_integration",
        "client_visible": True,
        "environment": "sandbox",
        "allowed_scopes": (
            "ticket:read",
            "ticket:create",
            "workflow_status:read",
        ),
        "forbidden_scopes": (
            "ticket:close",
            "billing:update",
            "payment:execute",
            "production_write",
        ),
        "read_only": False,
        "write_allowed": True,
        "restricted_allowed": False,
        "requires_enterprise_plan": True,
        "requires_integration_readiness": True,
        "requires_supervisor_for_write": True,
        "production_allowed": False,
        "runtime_connector_approved": False,
        "next_action": "Supervisor must approve sandbox ticketing scope first.",
    },
    {
        "profile_id": "service_integration_billing_read",
        "display_name": "Service Integration - Billing Read",
        "base_key_profile": "service_integration",
        "client_visible": True,
        "environment": "sandbox",
        "allowed_scopes": (
            "billing_account:read",
            "invoice_status:read",
            "usage_summary:read",
        ),
        "forbidden_scopes": (
            "billing:update",
            "invoice:issue",
            "payment:execute",
            "production_write",
        ),
        "read_only": True,
        "write_allowed": False,
        "restricted_allowed": False,
        "requires_enterprise_plan": True,
        "requires_integration_readiness": True,
        "requires_supervisor_for_write": True,
        "production_allowed": False,
        "runtime_connector_approved": False,
        "next_action": "Collect billing API documentation for readiness review.",
    },
    {
        "profile_id": "telecom_operations_sandbox",
        "display_name": "Telecom Operations Sandbox",
        "base_key_profile": "service_integration",
        "client_visible": True,
        "environment": "sandbox",
        "allowed_scopes": (
            "crm_customer:read",
            "ticket:read",
            "order_status:read",
            "network_assurance_event:create",
        ),
        "forbidden_scopes": (
            "crm_customer:update",
            "billing:update",
            "payment:execute",
            "production_write",
        ),
        "read_only": False,
        "write_allowed": True,
        "restricted_allowed": False,
        "requires_enterprise_plan": True,
        "requires_integration_readiness": True,
        "requires_supervisor_for_write": True,
        "production_allowed": False,
        "runtime_connector_approved": False,
        "next_action": "Complete telecom readiness blockers before sandbox approval.",
    },
    {
        "profile_id": "document_metadata_access",
        "display_name": "Document Metadata Access",
        "base_key_profile": "service_integration",
        "client_visible": True,
        "environment": "sandbox",
        "allowed_scopes": (
            "document_metadata:read",
            "document_status:read",
            "workflow_status:read",
        ),
        "forbidden_scopes": (
            "document_content:read",
            "document:delete",
            "document:update",
            "production_write",
        ),
        "read_only": True,
        "write_allowed": False,
        "restricted_allowed": False,
        "requires_enterprise_plan": True,
        "requires_integration_readiness": True,
        "requires_supervisor_for_write": True,
        "production_allowed": False,
        "runtime_connector_approved": False,
        "next_action": "Confirm metadata-only scope with supervisor.",
    },
    {
        "profile_id": "enterprise_core_status_read",
        "display_name": "Enterprise Core Status Read",
        "base_key_profile": "service_integration",
        "client_visible": True,
        "environment": "sandbox",
        "allowed_scopes": (
            "enterprise_case:read",
            "workflow_status:read",
            "integration_readiness:read",
        ),
        "forbidden_scopes": (
            "enterprise_case:update",
            "restricted_case:finalize",
            "connector_runtime:execute",
            "production_write",
        ),
        "read_only": True,
        "write_allowed": False,
        "restricted_allowed": False,
        "requires_enterprise_plan": True,
        "requires_integration_readiness": True,
        "requires_supervisor_for_write": True,
        "production_allowed": False,
        "runtime_connector_approved": False,
        "next_action": "Use this profile for discovery before scoped integration work.",
    },
    {
        "profile_id": "enterprise_telecom_conformance_read",
        "display_name": "Enterprise Telecom Conformance Read",
        "base_key_profile": "service_integration",
        "client_visible": True,
        "environment": "sandbox",
        "allowed_scopes": (
            "crm:read",
            "ticket:read",
            "helpdesk:read",
            "order:preview",
            "network:read",
            "network:diagnostics_read",
        ),
        "forbidden_scopes": (
            "customer:update",
            "ticket:create",
            "ticket:update",
            "order:create_with_approval",
            "order:execute",
            "network:write",
            "production_write",
            "connector_runtime:execute",
        ),
        "read_only": True,
        "write_allowed": False,
        "restricted_allowed": False,
        "requires_enterprise_plan": True,
        "requires_integration_readiness": True,
        "requires_supervisor_for_write": True,
        "production_allowed": False,
        "runtime_connector_approved": False,
        "next_action": (
            "Complete supervisor-approved sandbox conformance "
            "qualification before task-scoped key issuance."
        ),
    },
)


def list_api_key_operational_profiles(
    *, client_visible_only: bool = True
) -> tuple[dict[str, object], ...]:
    profiles = API_KEY_OPERATIONAL_PROFILES
    if client_visible_only:
        profiles = tuple(profile for profile in profiles if profile["client_visible"])
    return tuple(deepcopy(profile) for profile in profiles)


def get_api_key_operational_profile(profile_id: str) -> dict[str, object]:
    for profile in API_KEY_OPERATIONAL_PROFILES:
        if profile["profile_id"] == profile_id:
            return deepcopy(profile)
    raise KeyError(f"Unknown API key operational profile: {profile_id}")


def api_key_operational_profiles_payload() -> dict[str, object]:
    profiles = list_api_key_operational_profiles(client_visible_only=True)
    return {
        "ok": True,
        "catalog": "api_key_operational_profiles",
        "profile_count": len(profiles),
        "production_allowed": False,
        "runtime_connector_approved": False,
        "profiles": profiles,
    }
