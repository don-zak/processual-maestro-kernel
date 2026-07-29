# Group 2 — Settings Top-Up UI/UX Review

## Placement decision

Quota top-up purchase belongs inside the authenticated customer settings area:

```text
Settings → Billing and Usage → Additional Maestro units
```

It must not be implemented as an unrelated public page or a standalone visual
experience.

## Information hierarchy

The settings section must show, in this order:

1. Active plan and current monthly Maestro allowance.
2. Remaining units and current billing-cycle date.
3. Additional-unit bundle size.
4. Controlled bundle-count selector.
5. Total additional units.
6. Price per bundle and total price.
7. Validity and rollover policy.
8. Upgrade comparison when upgrading is cheaper or equivalent.
9. Review and confirmation action.

## Interaction design

Use the existing Settings layout, typography, spacing, cards, controls, alerts,
and confirmation patterns.

The quantity selector must be controlled:

```text
[-]  3 bundles  [+]
30,000 additional units
Total price: $177.00
```

A free-form arbitrary quantity field is not allowed. The user may select only
integer multiples between the policy minimum and maximum.

## Required states

- loading;
- ready;
- empty or no active subscription;
- invalid quantity;
- upgrade recommended;
- payment unavailable;
- pending;
- success;
- error;
- disabled.

## Content requirements

The UI must clearly explain:

- what a Maestro unit represents;
- the plan's current monthly allowance;
- the minimum additional bundle;
- the number of selected bundles;
- total units and total price;
- whether the units expire or roll over;
- that provider usage remains BYOK;
- whether upgrading is better value.

## Quality acceptance gate

Implementation is rejected unless it:

- matches the program's existing Settings design system;
- is responsive on mobile and desktop;
- supports keyboard and screen-reader use;
- prevents accidental duplicate submission;
- communicates recalculation and pending states;
- provides confirmation before purchase;
- separates top-up purchase from plan cancellation and unrelated settings;
- contains no temporary or prototype UI.

## Current safety state

```text
Settings top-up visible: false
Purchase enabled: false
Checkout enabled: false
Standalone top-up page allowed: false
Actual Settings design system required: true
```
