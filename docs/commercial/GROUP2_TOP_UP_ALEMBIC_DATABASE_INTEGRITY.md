# Group 2 â€” Top-Up Alembic Migration and Database Integrity

Creates the four commercial top-up persistence tables and enforces unique
order, provider-payment, grant, and audit identifiers.

Database tests verify foreign keys, one grant per order, and append-only ORM
guards for audit records.

This change introduces schema only. Checkout, verification, runtime storage,
grant execution, reconciliation, and customer-visible commercial behavior all
remain disabled.