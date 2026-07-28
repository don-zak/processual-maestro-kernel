# Maestro Calibration Method R1

## Status

- Version: `maestro-unit-v1-calibration-a`
- Shadow only: yes
- Approved for quota: no
- Approved for invoicing: no
- Approved for checkout: no

## Safety boundary

This package defines calibration contracts and reference workloads only. It must not alter legacy quota enforcement, checkout, prices, allowances, subscriptions, payment activation, or runtime middleware.

## Initial candidate weights

- Base completed execution: 1.00 unit
- Successful external integrations: 1.00 per 4 actions
- Equivalent document pages: 1.00 per 25 pages
- Data records: 1.00 per 1,000 records
- Verification items: 1.00 per 25 items
- Standard supervision gate: 2.00
- Extended supervision gate: 5.00
- Excess storage: 0.50 per GB-month

These are calibration hypotheses, not commercial values.

## Resource bands

- Normal: 1.00
- Heavy: 1.25
- Extreme: 1.50
- Beyond 1.50: custom workload; no automatic settlement

## Conservative billing rules

- Platform failure settles zero.
- Duplicate delivery settles zero.
- Internal retry must not duplicate settlement.
- Cancellation before execution settles zero and releases reservation.
- Partial completion represents only completed measurable components.
- Unknown failure requires review and does not auto-settle.
- Human specialist review is a professional service, not Maestro Units.

## Exit gate

R1 is accepted only when contracts are immutable, Decimal-only, deterministic, serializable, isolated from runtime enforcement, and all catalog and validation tests pass.
