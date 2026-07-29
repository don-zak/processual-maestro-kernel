# Group 2 â€” Top-Up Order, Payment Verification, and Unit Grant

## Purpose

Defines the lifecycle after a customer confirms a quota top-up from Settings.

## Order lifecycle

```text
draft
â†’ awaiting confirmation
â†’ awaiting payment
â†’ payment pending
â†’ payment verified
â†’ grant pending
â†’ granted
```

Failure, rejection, cancellation, and retry paths remain explicit.

## Payment verification

A payment may be accepted only when:

- the payment belongs to the exact order;
- the provider reference is present;
- the verified amount exactly matches the order total;
- the currency is USD;
- immutable verification evidence is recorded;
- the verification result is explicit.

Payment success must not automatically be treated as unit-grant completion.

## Exactly-once unit grant

Every grant uses a deterministic idempotency key derived from:

- top-up order ID;
- client order idempotency key.

A repeated grant request returns a duplicate result and must not add units again.

## Grant blocking conditions

Unit grant is blocked when:

- the customer did not confirm the order;
- payment belongs to another order;
- payment is pending or rejected;
- amount or currency does not match;
- immutable verification evidence is missing;
- the grant idempotency key already exists;
- runtime grant execution is disabled.

## UI/UX implications

The Settings UI must distinguish:

- payment pending;
- payment verified;
- unit grant pending;
- units granted;
- payment rejected;
- grant failed;
- duplicate request safely ignored.

The success state is shown only after the unit grant is confirmed, not merely
after payment verification.

## Current safety state

```text
Status: draft_review
Order creation: false
Payment verification: false
Unit-grant execution: false
Order persistence: false
Audit persistence: false
Idempotency required: true
Immutable audit required: true
Exactly-once grant required: true
```