# Group 2 â€” Settings Top-Up Checkout Journey

## Entry point

The purchase journey starts only from:

```text
Settings â†’ Billing and Usage â†’ Additional Maestro units
```

The customer first selects a valid bundle multiple, reviews the calculated
price, and then proceeds to payment-channel review.

## Channel policy

For an active subscription:

- the Tunisian local channel is shown only for an eligible Tunisian billing
  address;
- Lemon Squeezy remains the general channel;
- the local route must never replace or force the general route;
- channel selection must be explicit;
- no channel is available while commercial activation remains disabled.

## Journey states

- loading;
- eligibility required;
- channel selection;
- review;
- confirmation required;
- payment pending;
- payment succeeded;
- payment failed;
- verification pending;
- grant pending;
- completed;
- cancelled;
- disabled.

## Confirmation and safety

Before payment, the Settings UI must show:

- active plan;
- additional bundle count and units;
- total price;
- selected payment channel;
- expiry or rollover policy;
- upgrade recommendation when relevant;
- explicit confirmation action.

Duplicate submission protection is mandatory. Refreshing or repeating the
confirmation must not create duplicate orders, charges, or unit grants.

## UI/UX requirements

The actual frontend must reuse the current Settings design system and clearly
separate:

- quantity selection;
- price review;
- channel selection;
- payment status;
- unit-grant status.

Pending payment and pending unit grant are different states and must not be
presented as completed.

## Current safety state

```text
Status: draft_review
Checkout session creation: false
Payment collection: false
Order persistence: false
Unit grant: false
Tunisia local channel: false
Lemon Squeezy channel: false
```