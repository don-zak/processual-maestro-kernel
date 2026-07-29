# Group 2 â€” SQLAlchemy Top-Up Persistence

## Implemented components

- SQLAlchemy models for top-up orders, payment evidence, grants, and audit rows.
- Async repositories following the existing project persistence style.
- Async Unit of Work with rollback-on-failure behavior.
- Unique order and grant idempotency constraints.
- Unique provider payment reference.
- One authoritative grant row per order.
- Append-only audit protection at ORM event level.

## Atomicity boundary

The future grant application service must add the grant row and its audit row
inside the same Unit of Work and commit once. A partial grant without its audit
event is prohibited.

## Current activation state

The SQLAlchemy implementation exists, but commercial runtime flags remain
disabled. No checkout, payment verification, storage, reconciliation, or unit
grant is activated by this change.

## Deferred work

A dedicated Alembic migration and database integration tests are required in
the next change after model/repository review passes.