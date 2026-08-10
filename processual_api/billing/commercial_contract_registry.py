"""Central version registry for Stage 2 commercial authority contracts.

The registry provides one immutable inventory and digest for authority-bearing
commercial contracts. It does not enable any runtime commercial capability.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final

from processual_api.billing.assessment_plan_fulfillment import (
    ASSESSMENT_PLAN_FULFILLMENT_VERSION,
)
from processual_api.billing.commercial_academic_institution_authority import (
    ACADEMIC_INSTITUTION_AUTHORITY_VERSION,
)
from processual_api.billing.commercial_catalog_contracts import CATALOG_CONTRACT_VERSION
from processual_api.billing.commercial_event_contracts import COMMERCIAL_EVENT_CONTRACT_VERSION
from processual_api.billing.commercial_top_up_application_service import (
    TOP_UP_APPLICATION_SERVICE_VERSION,
)
from processual_api.billing.commercial_top_up_event_ledger import TOP_UP_EVENT_LEDGER_VERSION
from processual_api.billing.commercial_top_up_transition_authority import (
    TOP_UP_TRANSITION_AUTHORITY_VERSION,
)

COMMERCIAL_AUTHORITY_BUNDLE_VERSION: Final = "2026-08-b2-commercial-authority-bundle-v1"


@dataclass(frozen=True, slots=True)
class CommercialContractVersion:
    contract: str
    version: str

    def __post_init__(self) -> None:
        if not self.contract.strip():
            raise ValueError("contract must not be blank")
        if not self.version.strip():
            raise ValueError("version must not be blank")


_CONTRACT_VERSIONS = {
    "academic_institution_authority": ACADEMIC_INSTITUTION_AUTHORITY_VERSION,
    "assessment_plan_fulfillment": ASSESSMENT_PLAN_FULFILLMENT_VERSION,
    "catalog": CATALOG_CONTRACT_VERSION,
    "commercial_event": COMMERCIAL_EVENT_CONTRACT_VERSION,
    "top_up_application_service": TOP_UP_APPLICATION_SERVICE_VERSION,
    "top_up_event_ledger": TOP_UP_EVENT_LEDGER_VERSION,
    "top_up_transition_authority": TOP_UP_TRANSITION_AUTHORITY_VERSION,
}
COMMERCIAL_CONTRACT_VERSIONS: Final = MappingProxyType(_CONTRACT_VERSIONS)


def validate_commercial_contract_registry() -> tuple[CommercialContractVersion, ...]:
    records = tuple(
        CommercialContractVersion(contract=name, version=version)
        for name, version in sorted(COMMERCIAL_CONTRACT_VERSIONS.items())
    )
    if len(records) != len(COMMERCIAL_CONTRACT_VERSIONS):
        raise ValueError("commercial contract registry contains duplicate contracts")
    return records


def commercial_contract_registry_digest() -> str:
    material = "\n".join(
        f"{record.contract}={record.version}"
        for record in validate_commercial_contract_registry()
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def build_commercial_contract_registry_status() -> dict[str, object]:
    records = validate_commercial_contract_registry()
    return {
        "bundle_version": COMMERCIAL_AUTHORITY_BUNDLE_VERSION,
        "contract_count": len(records),
        "registry_digest": commercial_contract_registry_digest(),
        "contracts": [
            {"contract": record.contract, "version": record.version}
            for record in records
        ],
        "runtime_enablement_changed": False,
    }


validate_commercial_contract_registry()


__all__ = [
    "COMMERCIAL_AUTHORITY_BUNDLE_VERSION",
    "COMMERCIAL_CONTRACT_VERSIONS",
    "CommercialContractVersion",
    "build_commercial_contract_registry_status",
    "commercial_contract_registry_digest",
    "validate_commercial_contract_registry",
]
