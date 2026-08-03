# Maestro Pricing and Calculation Reference

## Status

This document identifies the canonical implementation files used to calculate:

1. Maestro usage units.
2. Task consumption.
3. Monthly plan allowances.
4. Estimated monthly operating cost.
5. Minimum and recommended pricing.
6. Selected monthly and yearly prices.
7. Overage prices.
8. Public price visibility.

The Python implementation remains the source of truth. This document and the
generated JSON snapshot are review artifacts only.

## Public price policy

Prices publicly displayed through Enterprise Pilot:

| Plan | Monthly USD |
|---|---:|
| Academic | 29 |
| Starter | 49 |
| Enterprise Integration Starter | 259 |
| Business | 519 |
| Enterprise Pilot | 2,790 |

Plans requiring assessment without a public numeric price:

- Enterprise Core
- Enterprise Scale
- Enterprise Strategic

Internal prices for assessment plans remain available to authorized calculation
and commercial-review workflows.

## Canonical implementation files

- `processual_api/billing/maestro_group1_pricing_review.py`
- `processual_api/billing/maestro_group1_selected_pricing.py`
- `processual_api/billing/commercial_catalog_contracts.py`
- `processual_api/billing/usage_pricing.py`
- `processual_api/billing/commercial_quota_top_up_contracts.py`
- `processual_api/billing/offer_pricebook.py`
- `processual_api/billing/subscription_catalog.py`

Additional task-to-unit calculation files must be added after the repository-wide
inventory is reviewed.

## Calculation chain

The intended review chain is:

`task definition`
→ `task consumption`
→ `Maestro usage units`
→ `monthly usage`
→ `plan allowance`
→ `overage`
→ `estimated operating cost`
→ `minimum/recommended price`
→ `selected commercial price`

## Generated reference

See:

- `docs/audits/A3_PRICING_CALCULATION_SNAPSHOT.json`
- `docs/audits/A3_PRICING_CALCULATION_FILE_INVENTORY.txt`

The snapshot includes SHA-256 hashes for the canonical source files.
