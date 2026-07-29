# Group 2 — Quota Top-Up Purchase Contracts

## Purpose

Defines how customers may request additional Maestro units using the same
commercial purchase experience as quota purchases and plan upgrades.

## Core policy

Additional units are purchased as integer multiples of a plan-specific minimum
bundle. Arbitrary quantities are rejected.

```text
Requested units = bundle units × bundle count
```

The customer interface must display:

- bundle size;
- selected bundle count;
- total additional units;
- price per bundle;
- total price before confirmation;
- validity and rollover policy;
- unavailable, invalid, pending, success, and failure states;
- upgrade guidance when moving to a higher plan is cheaper or equivalent.

## Draft minimum bundles

| Plan | Minimum bundle |
|---|---:|
| Academic | 5,000 units |
| Starter | 10,000 units |
| Enterprise Integration Starter | 25,000 units |
| Business | 25,000 units |
| Enterprise Pilot | 100,000 units |
| Enterprise Core | 250,000 units |
| Enterprise Scale | 500,000 units |
| Enterprise Strategic | 500,000 units |

## Pricing rule

The draft bundle price is derived from the selected plan's approved-review
overage rate:

```text
Bundle price = overage price per 1,000 units × bundle units / 1,000
```

No discount is silently applied. Any future top-up discount must be an explicit
commercial decision with floor and margin validation.

## Upgrade recommendation

When the total top-up price reaches or exceeds the monthly difference to the
next relevant plan, the UI must recommend the upgrade before confirmation.
The customer remains free to review the available option subject to commercial
eligibility.

## UI/UX acceptance gate

The actual frontend must reuse the program design system and include:

- stepper or controlled bundle selector;
- no unrestricted arbitrary quantity field;
- keyboard and screen-reader accessibility;
- mobile and desktop responsiveness;
- explicit minimum and maximum validation;
- live total-price recalculation;
- clear upgrade comparison;
- loading, error, unavailable, pending, success, and failure states.

## Safety status

```text
Status: draft_review
Top-up purchase enabled: false
Top-up checkout enabled: false
Top-up grant enabled: false
Top-up persistence enabled: false
Active subscription required: true
Integer multiples only: true
Seat based: false
```
