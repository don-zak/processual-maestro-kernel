# Group 2 — Commercial UI/UX Architecture Boundary

## Inventory conclusion

No frontend framework or design-system marker was discovered in this public
repository during the Group 2 foundation inventory.

This repository must therefore not create a standalone commercial interface
that could diverge from the actual program UI.

## Binding implementation rule

The public repository may provide:

- commercial API and presentation contracts;
- selected pricing data;
- explicit loading, empty, error, disabled, success, and denial states;
- authority and eligibility decisions;
- accessibility-ready labels and semantic state metadata;
- tests for commercial and permission boundaries.

The visual frontend must be implemented only in the repository that contains
the program's actual design system, components, layout, typography, responsive
rules, and interaction patterns.

## Required surfaces

### Public pricing

Must present plans consistently with the program design system and must not
publish draft prices as approved.

### Subscription checkout

Must present the optional Tunisian local route only for eligible Tunisian
billing addresses at the start of the payment journey. Lemon Squeezy remains
available as the general route.

### Admin Marketplace

Must remain restricted to the platform administrator. Delegated supervisors
must receive an explicit denial state. Commercial actions require their
existing security and step-up controls.

## UI/UX acceptance gate

Implementation is rejected unless it includes:

- loading;
- empty;
- error;
- success;
- disabled;
- permission-denied states where applicable;
- responsive behavior;
- keyboard and screen-reader accessibility;
- visual consistency with the existing program;
- no temporary or prototype interface;
- no confusion between public customer flows and protected admin controls.

## Commercial safety boundary

```text
Pricing approved: false
Checkout enabled: false
Invoicing enabled: false
Settlement enabled: false
Quota enforcement enabled: false
Selected pricing status: draft_review
```
