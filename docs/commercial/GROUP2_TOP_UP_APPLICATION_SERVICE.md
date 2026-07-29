# Group 2 Ã¢â‚¬â€ Atomic Top-Up Application Service

## Scope

This slice introduces the asynchronous application-service boundary that
coordinates:

- idempotent order creation;
- immutable order-created audit evidence;
- verified payment evidence;
- exactly-once grant decisions;
- atomic payment, grant, and audit persistence;
- rollback on conflict or partial failure.

## Fail-closed runtime policy

The default application-service policy is constructed from the existing
commercial runtime constants. Every production-facing capability remains
disabled:

- order creation;
- payment verification;
- grant execution;
- order storage;
- payment evidence storage;
- grant storage;
- audit storage.

The service refuses to open a Unit of Work when a required capability is
disabled.

## Atomicity

Payment evidence, a granted decision, the order state transition, and both
audit records are staged in one asynchronous Unit of Work and committed once.
Any conflict exits without commit and relies on the Unit of Work rollback
contract.

## Idempotency

- Order idempotency keys return the existing equivalent order.
- Reuse with different commercial data fails closed.
- Provider payment references cannot move between orders.
- A replay after the atomic payment/grant commit returns the existing result
  without creating another payment, grant, audit event, or commit.

## Isolation

The service contains no network client, payment-provider client, Redis client,
entitlement mutation, or quota-balance mutation.

Actual balance mutation remains outside this slice and remains disabled.