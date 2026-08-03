# Pull Request Execution File

## Repository

`don-zak/processual-maestro-kernel`

## Source Branch

`feat/a3-plan-led-registration-journey`

## Target Branch

`main`

## Commit

`faab2db Add plan-led registration journey and pricing reference`

## PR Title

`Add plan-led registration journey and pricing reference`

## PR Body

### Summary

This pull request introduces the A3 plan-led registration journey and establishes the selected Maestro pricing model as the server-owned reference for public plan presentation.

### Changes

- adds the public plan journey catalog
- exposes `GET /billing/public-plan-journey`
- adds the public `/plans` page
- adds the public `/offer/{plan_id}` page
- presents plan names first, before offer details
- displays public monthly prices through Enterprise Pilot
- sends Enterprise Core, Enterprise Scale, and Enterprise Strategic to assessment without exposing their numeric prices
- keeps checkout disabled and provider costs excluded
- loads plan and price data from the server-owned catalog
- avoids embedding selected prices directly in HTML
- adds pricing calculation snapshots and audit references
- records selected monthly prices and overage prices
- records the canonical files used for workload, unit, cost, quota, and pricing calculations
- adds unit, route, page, and UTF-8 regression coverage

### Public Pricing Policy

| Plan | Public monthly price |
|---|---:|
| Academic | USD 29 |
| Starter | USD 49 |
| Business | USD 519 |
| Enterprise Integration Starter | USD 259 |
| Enterprise Pilot | USD 2,790 |
| Enterprise Core | Assessment required |
| Enterprise Scale | Assessment required |
| Enterprise Strategic | Assessment required |

Numeric prices for post-Pilot plans remain available only to authorized internal calculation and commercial review workflows.

### Public Journey

1. User opens `/plans`.
2. User selects a plan-name card.
3. User opens `/offer/{plan_id}`.
4. The page retrieves the selected offer from `/billing/public-plan-journey`.
5. Publicly priced plans continue to registration.
6. Post-Pilot plans continue to the assessment journey.

### Pricing and Calculation References

The pull request adds:

- `docs/audits/A3_PRICING_CALCULATION_FILE_INVENTORY.txt`
- `docs/audits/A3_PRICING_CALCULATION_REFERENCE.md`
- `docs/audits/A3_PRICING_CALCULATION_SNAPSHOT.json`
- `docs/audits/A3_SELECTED_MONTHLY_PRICES.csv`
- `tools/audits/a3_pricing_calculation_snapshot.py`

The Python implementation remains the canonical source of truth. Generated documentation and snapshots are review artifacts.

### Validation

- Ruff checks passed
- 17 targeted tests passed
- public journey unit tests passed
- public journey route tests passed
- plan-led page tests passed
- UTF-8 encoding regression tests passed
- `git show --check` passed
- branch pushed successfully to origin

### Test Command

```powershell
.\.venv\Scripts\python.exe -m pytest -q `
  tests\test_public_plan_journey_a3.py `
  tests\test_public_plan_journey_route_a3.py `
  tests\test_plan_led_registration_pages_a3.py `
  tests\test_static_utf8_encoding_regression.py
```

Expected result:

```text
17 passed
```

### Review Checklist

- [ ] Confirm the eight public plan identities and display order.
- [ ] Confirm public prices are visible only through Enterprise Pilot.
- [ ] Confirm Core, Scale, and Strategic show assessment messaging.
- [ ] Confirm no selected prices are hardcoded in HTML.
- [ ] Confirm `/billing/public-plan-journey` remains publicly readable.
- [ ] Confirm checkout remains fail-closed.
- [ ] Confirm provider costs remain excluded.
- [ ] Confirm audit snapshots match the canonical Python pricing implementation.
- [ ] Confirm `/plans` and `/offer/{plan_id}` align with the intended registration journey.
- [ ] Confirm CI passes before merge.

### Merge Strategy

Use **Squash and merge** unless repository policy requires preserving the current commit.

Suggested squash commit message:

```text
Add plan-led registration journey and pricing reference
```

### Post-Merge Work

- pass the selected `plan` from `/offer/{plan_id}` into `/register`
- preserve the selected plan throughout registration and email verification
- build the separate assessment intake flow for post-Pilot plans
- perform browser-level UI/UX review for desktop and mobile
- add end-to-end coverage for plan selection through verified registration

## GitHub PR URL

`https://github.com/don-zak/processual-maestro-kernel/compare/main...feat/a3-plan-led-registration-journey?expand=1`
