# Group 2 â€” Top-Up Persistence, Immutable Audit, and Reconciliation

## Purpose

Defines the repository ports and reconciliation rules required before top-up
orders, payment evidence, grant records, and audit events may be persisted.

## Persistence boundaries

Separate repositories are required for:

- top-up orders;
- payment-verification evidence;
- unit-grant decisions;
- append-only audit events.

A unit of work coordinates them so that grant and audit persistence can become
atomic when runtime execution is eventually approved.

## Uniqueness constraints

The future storage implementation must enforce:

- unique client order idempotency key;
- unique provider payment reference;
- unique grant idempotency key;
- one authoritative grant outcome per order;
- immutable audit rows.

## Append-only audit

Audit records must never be updated or deleted. Corrections are represented by
new events. Every event includes:

- order ID;
- action;
- timezone-aware occurrence time;
- actor reference;
- immutable evidence reference;
- payload digest.

## Reconciliation states

- consistent;
- payment without grant;
- grant without payment;
- duplicate grant;
- missing order;
- manual review.

Any payment/grant mismatch must be surfaced to protected commercial operations
and must not be represented to the customer as completed.

## UI/UX implications

Settings must show a truthful status based on the reconciled lifecycle:

- payment pending;
- payment verified;
- grant pending;
- completed;
- needs review;
- failed.

A successful payment with a missing grant remains pending or under review, not
completed.

## Current safety state

```text
Status: draft_review
Order storage: false
Payment-evidence storage: false
Grant storage: false
Audit storage: false
Reconciliation execution: false
Append-only audit required: true
Unique order idempotency required: true
Unique grant idempotency required: true
Atomic grant and audit required: true
```