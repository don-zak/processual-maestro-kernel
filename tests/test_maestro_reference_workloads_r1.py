from decimal import Decimal

from processual_api.billing.maestro_calibration_contracts import (
    MaestroBillingDisposition,
    MaestroFailureOwner,
    MaestroResourceBand,
)
from processual_api.billing.maestro_reference_workloads import (
    REFERENCE_WORKLOADS,
    workloads_by_id,
)


def test_catalog_contains_exactly_36_unique_workloads():
    assert len(REFERENCE_WORKLOADS) == 36
    ids = [item.workload_id for item in REFERENCE_WORKLOADS]
    assert len(ids) == len(set(ids))


def test_catalog_lookup_is_complete():
    lookup = workloads_by_id()
    assert set(lookup) == {item.workload_id for item in REFERENCE_WORKLOADS}


def test_platform_failures_and_duplicates_settle_zero():
    lookup = workloads_by_id()
    assert lookup["AUT-F-01"].expected_failure_owner is MaestroFailureOwner.PLATFORM
    assert lookup["AUT-F-01"].expected_settled_units == Decimal(0)
    assert lookup["INT-D-01"].expected_settled_units == Decimal(0)
    assert lookup["INT-D-01"].expected_disposition is MaestroBillingDisposition.NON_BILLABLE


def test_internal_retry_does_not_double_settle():
    workload = workloads_by_id()["AUT-R-01"]
    assert workload.expected_raw_units == Decimal(1)
    assert workload.expected_settled_units == Decimal(1)


def test_cancellation_and_unknown_failure_are_conservative():
    lookup = workloads_by_id()
    assert lookup["MIX-C-01"].expected_settled_units == Decimal(0)
    assert lookup["MIX-U-01"].expected_settled_units == Decimal(0)
    assert lookup["MIX-U-01"].expected_disposition is MaestroBillingDisposition.REVIEW_REQUIRED


def test_resource_modifier_examples_respect_v1_cap():
    lookup = workloads_by_id()
    assert lookup["AUT-L-01"].expected_settled_units == Decimal("11.25")
    assert lookup["MIX-H-01"].expected_settled_units == Decimal(15)
    assert lookup["MIX-X-01"].resource_band is MaestroResourceBand.CUSTOM
    assert lookup["MIX-X-01"].expected_settled_units == Decimal(0)


def test_partial_completion_only_represents_completed_quantities():
    lookup = workloads_by_id()
    assert lookup["INT-P-01"].quantities.integration_actions == Decimal(5)
    assert lookup["DOC-P-01"].quantities.equivalent_pages == Decimal(60)
    assert lookup["DAT-P-01"].quantities.records_processed == Decimal(7200)
