from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Final, Protocol

from processual_api.admin_marketplace.assessment_commercial_terms_persistence import (
    AdminMarketAssessmentCommercialTerms,
)
from processual_api.admin_marketplace.assessment_quota_profile_service import (
    AssessmentQuotaProfileRepository,
    ensure_assessment_quota_profile_in_unit,
)
from processual_api.billing.assessment_activation_preparation import ApprovedAssessmentOutcome

ASSESSMENT_COMMERCIAL_TERMS_VERSION: Final = "2026-08-assessment-commercial-terms-v1"
_ALLOWED_PRICE_SOURCES: Final = frozenset({"assessment", "contract"})
_ALLOWED_BILLING_INTERVALS: Final = frozenset({"monthly", "annual", "one_time", "custom"})


class AssessmentCommercialTermsError(ValueError):
    """Approved assessment commercial terms are missing, invalid, or conflicting."""


class AssessmentCommercialTermsConflictError(AssessmentCommercialTermsError):
    """A durable terms binding conflicts with the requested authoritative terms."""


@dataclass(frozen=True, slots=True)
class ApprovedAssessmentCommercialTerms:
    price_source: str
    source_reference: str
    currency: str
    billing_interval: str
    amount_minor_units: int
    approved_by: str
    approval_reference: str
    effective_at: datetime
    terms_version: str = ASSESSMENT_COMMERCIAL_TERMS_VERSION


@dataclass(frozen=True, slots=True)
class AssessmentCommercialTermsResult:
    record: AdminMarketAssessmentCommercialTerms
    replayed: bool


class _AssessmentCommercialTermsRepository(Protocol):
    async def get_by_binding_hash(
        self,
        assessment_binding_hash: str,
        *,
        for_update: bool = False,
    ) -> AdminMarketAssessmentCommercialTerms | None: ...

    async def get_by_approval_reference(
        self,
        approval_reference: str,
        *,
        for_update: bool = False,
    ) -> AdminMarketAssessmentCommercialTerms | None: ...

    def add(self, terms: AdminMarketAssessmentCommercialTerms) -> None: ...


class AssessmentCommercialTermsUnitOfWork(Protocol):
    assessment_quota_profiles: AssessmentQuotaProfileRepository
    assessment_commercial_terms: _AssessmentCommercialTermsRepository

    async def __aenter__(self) -> AssessmentCommercialTermsUnitOfWork: ...
    async def __aexit__(self, exc_type, exc, traceback) -> None: ...
    async def commit(self) -> None: ...


def _required(value: str, name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise AssessmentCommercialTermsError(f"{name} is required")
    return normalized


def _normalize_currency(value: str) -> str:
    currency = _required(value, "currency").upper()
    if len(currency) != 3 or not currency.isalpha():
        raise AssessmentCommercialTermsError("currency must be a three-letter alphabetic code")
    return currency


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _payload_digest(payload: dict[str, object]) -> str:
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )
    return _sha256(canonical)


def _normalized_payload(
    *,
    assessment_id: str,
    customer_ref: str,
    public_plan_id: str,
    assessment_binding_hash: str,
    terms: ApprovedAssessmentCommercialTerms,
) -> dict[str, object]:
    price_source = _required(terms.price_source, "price_source").lower()
    if price_source not in _ALLOWED_PRICE_SOURCES:
        raise AssessmentCommercialTermsError("price_source must be assessment or contract")

    billing_interval = _required(terms.billing_interval, "billing_interval").lower()
    if billing_interval not in _ALLOWED_BILLING_INTERVALS:
        raise AssessmentCommercialTermsError("billing_interval is not supported")

    if terms.amount_minor_units < 0:
        raise AssessmentCommercialTermsError("amount_minor_units must be non-negative")
    if terms.effective_at.tzinfo is None:
        raise AssessmentCommercialTermsError("effective_at must be timezone-aware")

    terms_version = _required(terms.terms_version, "terms_version")
    source_reference = _required(terms.source_reference, "source_reference")
    approved_by = _required(terms.approved_by, "approved_by")
    approval_reference = _required(terms.approval_reference, "approval_reference")

    return {
        "assessment_id": assessment_id,
        "customer_ref": customer_ref,
        "public_plan_id": public_plan_id,
        "assessment_binding_hash": assessment_binding_hash,
        "terms_version": terms_version,
        "price_source": price_source,
        "source_reference": source_reference,
        "currency": _normalize_currency(terms.currency),
        "billing_interval": billing_interval,
        "amount_minor_units": terms.amount_minor_units,
        "approved_by": approved_by,
        "approval_reference": approval_reference,
        "effective_at": terms.effective_at.isoformat(),
    }


def _record_matches(
    record: AdminMarketAssessmentCommercialTerms,
    payload: dict[str, object],
    digest: str,
) -> bool:
    return (
        record.assessment_binding_hash == payload["assessment_binding_hash"]
        and record.assessment_id == payload["assessment_id"]
        and record.customer_ref == payload["customer_ref"]
        and record.public_plan_id == payload["public_plan_id"]
        and record.terms_version == payload["terms_version"]
        and record.price_source == payload["price_source"]
        and record.source_reference == payload["source_reference"]
        and record.currency == payload["currency"]
        and record.billing_interval == payload["billing_interval"]
        and record.amount_minor_units == payload["amount_minor_units"]
        and record.approved_by == payload["approved_by"]
        and record.approval_reference == payload["approval_reference"]
        and record.effective_at.isoformat() == payload["effective_at"]
        and record.payload_digest == digest
    )


async def ensure_assessment_commercial_terms_in_unit(
    *,
    outcome: ApprovedAssessmentOutcome,
    terms: ApprovedAssessmentCommercialTerms,
    unit: AssessmentCommercialTermsUnitOfWork,
) -> AssessmentCommercialTermsResult:
    quota = await ensure_assessment_quota_profile_in_unit(outcome=outcome, unit=unit)
    quota_record = quota.record
    payload = _normalized_payload(
        assessment_id=quota_record.assessment_id,
        customer_ref=quota_record.customer_ref,
        public_plan_id=quota_record.public_plan_id,
        assessment_binding_hash=quota_record.assessment_binding_hash,
        terms=terms,
    )
    digest = _payload_digest(payload)

    existing = await unit.assessment_commercial_terms.get_by_binding_hash(
        quota_record.assessment_binding_hash,
        for_update=True,
    )
    if existing is not None:
        if not _record_matches(existing, payload, digest):
            raise AssessmentCommercialTermsConflictError(
                "assessment commercial terms conflict with the durable binding"
            )
        return AssessmentCommercialTermsResult(record=existing, replayed=True)

    by_approval = await unit.assessment_commercial_terms.get_by_approval_reference(
        str(payload["approval_reference"]),
        for_update=True,
    )
    if by_approval is not None:
        if not _record_matches(by_approval, payload, digest):
            raise AssessmentCommercialTermsConflictError(
                "commercial approval reference is already bound to different terms"
            )
        return AssessmentCommercialTermsResult(record=by_approval, replayed=True)

    binding_hash = quota_record.assessment_binding_hash
    record = AdminMarketAssessmentCommercialTerms(
        terms_ref=f"assessment_terms_{binding_hash[:24]}",
        assessment_binding_hash=binding_hash,
        assessment_id=quota_record.assessment_id,
        customer_ref=quota_record.customer_ref,
        public_plan_id=quota_record.public_plan_id,
        terms_version=str(payload["terms_version"]),
        price_source=str(payload["price_source"]),
        source_reference=str(payload["source_reference"]),
        currency=str(payload["currency"]),
        billing_interval=str(payload["billing_interval"]),
        amount_minor_units=int(payload["amount_minor_units"]),
        approved_by=str(payload["approved_by"]),
        approval_reference=str(payload["approval_reference"]),
        effective_at=terms.effective_at,
        payload_digest=digest,
    )
    unit.assessment_commercial_terms.add(record)
    return AssessmentCommercialTermsResult(record=record, replayed=False)


def ensure_assessment_commercial_terms_factory(
    unit_of_work_factory: Callable[[], AssessmentCommercialTermsUnitOfWork],
):
    async def ensure(
        *,
        outcome: ApprovedAssessmentOutcome,
        terms: ApprovedAssessmentCommercialTerms,
    ) -> AssessmentCommercialTermsResult:
        async with unit_of_work_factory() as unit:
            result = await ensure_assessment_commercial_terms_in_unit(
                outcome=outcome,
                terms=terms,
                unit=unit,
            )
            if not result.replayed:
                await unit.commit()
            return result

    return ensure


__all__ = [
    "ASSESSMENT_COMMERCIAL_TERMS_VERSION",
    "ApprovedAssessmentCommercialTerms",
    "AssessmentCommercialTermsConflictError",
    "AssessmentCommercialTermsError",
    "AssessmentCommercialTermsResult",
    "AssessmentCommercialTermsUnitOfWork",
    "ensure_assessment_commercial_terms_factory",
    "ensure_assessment_commercial_terms_in_unit",
]
