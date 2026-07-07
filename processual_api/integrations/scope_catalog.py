"""Central integration scope catalog for external adapter readiness.

The catalog is declarative only. It derives supported scopes from the 11A sector
profiles and assigns review posture without creating credentials, endpoints,
HTTP clients, or customer-specific connectors.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType

from processual_api.integrations.sector_profiles import list_sector_profiles

READ_ACCESS = "read"
WRITE_ACCESS = "write"
RESTRICTED_ACCESS = "restricted"

LOW_RISK = "low"
HIGH_RISK = "high"
CRITICAL_RISK = "critical"

READ_KEY_PROFILES: tuple[str, ...] = (
    "external_partner",
    "service_integration",
)
WRITE_KEY_PROFILES: tuple[str, ...] = ("service_integration",)
RESTRICTED_KEY_PROFILES: tuple[str, ...] = ()


@dataclass(frozen=True)
class IntegrationScope:
    """A review-safe scope record for future adapter work."""

    scope_id: str
    domain: str
    action: str
    access_level: str
    risk_level: str
    sectors: tuple[str, ...]
    supported_key_profiles: tuple[str, ...]
    allowed_in_read_only_pilot: bool
    requires_enterprise_review: bool
    requires_supervisor_approval: bool
    requires_sandbox_before_production: bool
    production_allowed_without_approval: bool = False

    @property
    def is_restricted(self) -> bool:
        """Return whether the scope is restricted."""

        return self.access_level == RESTRICTED_ACCESS


def _split_scope(scope_id: str) -> tuple[str, str]:
    if ":" not in scope_id:
        return scope_id, "use"

    domain, action = scope_id.split(":", 1)
    return domain, action


def _risk_for_access(access_level: str) -> str:
    if access_level == READ_ACCESS:
        return LOW_RISK
    if access_level == WRITE_ACCESS:
        return HIGH_RISK
    return CRITICAL_RISK


def _key_profiles_for_access(access_level: str) -> tuple[str, ...]:
    if access_level == READ_ACCESS:
        return READ_KEY_PROFILES
    if access_level == WRITE_ACCESS:
        return WRITE_KEY_PROFILES
    return RESTRICTED_KEY_PROFILES


def _build_scope(
    *,
    scope_id: str,
    access_level: str,
    sector_id: str,
) -> IntegrationScope:
    domain, action = _split_scope(scope_id)

    return IntegrationScope(
        scope_id=scope_id,
        domain=domain,
        action=action,
        access_level=access_level,
        risk_level=_risk_for_access(access_level),
        sectors=(sector_id,),
        supported_key_profiles=_key_profiles_for_access(access_level),
        allowed_in_read_only_pilot=access_level == READ_ACCESS,
        requires_enterprise_review=True,
        requires_supervisor_approval=access_level != READ_ACCESS,
        requires_sandbox_before_production=True,
    )


def _merge_sector(
    *,
    existing: IntegrationScope,
    sector_id: str,
) -> IntegrationScope:
    sectors = tuple(sorted({*existing.sectors, sector_id}))

    return IntegrationScope(
        scope_id=existing.scope_id,
        domain=existing.domain,
        action=existing.action,
        access_level=existing.access_level,
        risk_level=existing.risk_level,
        sectors=sectors,
        supported_key_profiles=existing.supported_key_profiles,
        allowed_in_read_only_pilot=existing.allowed_in_read_only_pilot,
        requires_enterprise_review=existing.requires_enterprise_review,
        requires_supervisor_approval=existing.requires_supervisor_approval,
        requires_sandbox_before_production=existing.requires_sandbox_before_production,
        production_allowed_without_approval=(
            existing.production_allowed_without_approval
        ),
    )


def _add_scope(
    catalog: dict[str, IntegrationScope],
    *,
    scope_id: str,
    access_level: str,
    sector_id: str,
) -> None:
    if scope_id in catalog:
        existing = catalog[scope_id]
        if existing.access_level != access_level:
            raise ValueError(
                f"Scope {scope_id!r} has conflicting access levels: "
                f"{existing.access_level!r} and {access_level!r}."
            )
        catalog[scope_id] = _merge_sector(
            existing=existing,
            sector_id=sector_id,
        )
        return

    catalog[scope_id] = _build_scope(
        scope_id=scope_id,
        access_level=access_level,
        sector_id=sector_id,
    )


def _build_catalog() -> MappingProxyType[str, IntegrationScope]:
    catalog: dict[str, IntegrationScope] = {}

    for profile in list_sector_profiles():
        for scope_id in profile.read_scopes:
            _add_scope(
                catalog,
                scope_id=scope_id,
                access_level=READ_ACCESS,
                sector_id=profile.sector_id,
            )

        for scope_id in profile.write_scopes:
            _add_scope(
                catalog,
                scope_id=scope_id,
                access_level=WRITE_ACCESS,
                sector_id=profile.sector_id,
            )

        for scope_id in profile.restricted_scopes:
            _add_scope(
                catalog,
                scope_id=scope_id,
                access_level=RESTRICTED_ACCESS,
                sector_id=profile.sector_id,
            )

    return MappingProxyType(dict(sorted(catalog.items())))


INTEGRATION_SCOPE_CATALOG = _build_catalog()
SUPPORTED_INTEGRATION_SCOPES: tuple[str, ...] = tuple(
    INTEGRATION_SCOPE_CATALOG
)


def list_integration_scopes() -> tuple[IntegrationScope, ...]:
    """Return all integration scopes in stable order."""

    return tuple(
        INTEGRATION_SCOPE_CATALOG[scope_id]
        for scope_id in SUPPORTED_INTEGRATION_SCOPES
    )


def get_integration_scope(scope_id: str) -> IntegrationScope:
    """Return a scope by id."""

    normalized_scope_id = scope_id.strip().lower()

    try:
        return INTEGRATION_SCOPE_CATALOG[normalized_scope_id]
    except KeyError as exc:
        raise KeyError(
            f"Unsupported integration scope '{scope_id}'."
        ) from exc


def list_scopes_for_sector(sector_id: str) -> tuple[IntegrationScope, ...]:
    """Return scopes declared for a given sector."""

    normalized_sector_id = sector_id.strip().lower().replace("-", "_")

    return tuple(
        scope
        for scope in list_integration_scopes()
        if normalized_sector_id in scope.sectors
    )


def list_scopes_by_access_level(
    access_level: str,
) -> tuple[IntegrationScope, ...]:
    """Return scopes with the requested access level."""

    normalized_access_level = access_level.strip().lower()

    return tuple(
        scope
        for scope in list_integration_scopes()
        if scope.access_level == normalized_access_level
    )


def is_scope_allowed_in_read_only_pilot(scope_id: str) -> bool:
    """Return whether a scope is allowed in a read-only pilot."""

    return get_integration_scope(scope_id).allowed_in_read_only_pilot


def scope_requires_supervisor_approval(scope_id: str) -> bool:
    """Return whether a scope requires supervisor approval."""

    return get_integration_scope(scope_id).requires_supervisor_approval
