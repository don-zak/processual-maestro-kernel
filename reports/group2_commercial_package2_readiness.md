# Group 2 Commercial Package 2 Readiness

Generated at: 2026-07-30T16:25:24Z

## Repository state

- Branch: `feature/group2-entitlements-adaptive-commercial-runtime`
- Base commit: `b6f28ec53d55bd6154a82ed320da9fd90bf22b6a`
- Alembic head: `20260730_0016`
- Full Python test suite: passed
- Runtime activation: disabled

## Qualified capabilities

- Governed customer subscription checkout authority.
- USD authoritative pricing and optional TND settlement for eligible Tunisian addresses.
- Lemon Squeezy remains available as the alternative channel.
- Payment-provider events are evidence only.
- Provider signature and replay-protection boundaries.
- Platform-admin-only activation decisions with recent MFA step-up.
- Explicit delegated-supervisor denial.
- SQLAlchemy persistence and unit-of-work boundary.
- PostgreSQL 17 qualification for checkout, payment evidence, and activation decisions.
- Governed subscription-cycle grant command.
- Entitlement-ledger integration boundary.
- Admin Marketplace command bridge.
- Observe-only commercial telemetry contracts.
- Read-only reconciliation boundary.
- Clear UI state contracts for checkout, payment, review, success, and error states.

## Governing disabled boundaries

- Checkout runtime wiring: disabled.
- Provider webhook runtime: disabled.
- Provider event writes: disabled.
- Automatic activation: disabled.
- Direct provider-to-grant path: prohibited.
- Direct Admin Marketplace grant: prohibited.
- Quota enforcement: disabled.
- Adaptive load enforcement: disabled.
- Reconciliation auto-repair: disabled.
- Settlement execution: disabled.
- Commercial publication: disabled.

## Acceptance conclusion

Package 2 is structurally qualified and fail-closed. It may proceed to the UI and
observe-only runtime package, but it is not approved for production checkout,
provider webhooks, automatic activation, quota enforcement, invoicing, or
settlement.