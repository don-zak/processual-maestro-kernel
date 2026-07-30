# Group 2 — Consolidated Commercial Integration Package

## Decision

**READY_FOR_CONSOLIDATED_IMPLEMENTATION**

This document defines one integrated implementation package covering commercial subscription authority, checkout channels, entitlement consumption, Admin Marketplace controls, UI/UX, and observe-only runtime behavior.

## Baseline

- Branch: `feature/group2-entitlements-adaptive-commercial-runtime`
- Head: `f3039c66d90207598b8eb7151cd493f72e1f9504`
- Generated: `2026-07-30T15:02:53Z`
- Source files scanned: `784`
- Commercial-domain tests discovered: `79`
- Focused regression result: `597 passed, 7 skipped, 8 warnings in 20.01s`
- Missing discovery domains: `0`

## Governing constraints

- BYOK only; no platform-owned provider-key fallback.
- Checkout, commercial activation, quota enforcement, invoicing, and settlement remain disabled until explicit acceptance.
- Admin Marketplace remains exclusive to `platform_admin`.
- Delegated supervisors must be denied explicitly.
- Tunisian local payment is optional and limited to eligible Tunisian addresses.
- Lemon Squeezy remains an alternative path.
- Unused units remain usage rights, not cash or renewal credit.
- UI/UX quality is a governing acceptance condition.
- Work proceeds as one consolidated package, not fragmented micro-stages.

## Existing repository inventory

### subscription

- Matching files: 233
- `processual_api/main.py` — subscription, activation
- `processual_api/admin_marketplace/audit_contracts.py` — subscription, activation
- `processual_api/admin_marketplace/authority.py` — subscription
- `processual_api/admin_marketplace/contracts.py` — subscription, activation
- `processual_api/admin_marketplace/models.py` — subscription, activation
- `processual_api/admin_marketplace/__init__.py` — subscription, activation
- `processual_api/admin_marketplace/persistence/protocols.py` — subscription, activation
- `processual_api/admin_marketplace/persistence/repositories.py` — subscription, activation
- `processual_api/admin_marketplace/persistence/unit_of_work.py` — subscription, activation
- `processual_api/admin_marketplace/persistence/__init__.py` — subscription, activation
- `processual_api/billing/commercial_catalog_contracts.py` — subscription
- `processual_api/billing/commercial_entitlement_grant_posting_service.py` — subscription, activation
- `processual_api/billing/commercial_entitlement_ledger_boundaries.py` — subscription, billing cycle
- `processual_api/billing/commercial_entitlement_ledger_contracts.py` — subscription
- `processual_api/billing/commercial_entitlement_ledger_in_memory.py` — subscription
- `processual_api/billing/commercial_entitlement_ledger_models.py` — subscription
- `processual_api/billing/commercial_entitlement_ledger_persistence_contracts.py` — subscription
- `processual_api/billing/commercial_entitlement_ledger_repositories.py` — subscription
- `processual_api/billing/commercial_entitlement_ledger_schema_contracts.py` — subscription
- `processual_api/billing/commercial_entitlement_policy_contracts.py` — subscription
- Additional matching files omitted from Markdown: 213

### checkout

- Matching files: 198
- `processual_api/admin_marketplace/audit_contracts.py` — order
- `processual_api/admin_marketplace/authority.py` — order
- `processual_api/admin_marketplace/contracts.py` — order, invoice
- `processual_api/admin_marketplace/models.py` — order, invoice
- `processual_api/admin_marketplace/__init__.py` — order, invoice
- `processual_api/admin_marketplace/persistence/errors.py` — order
- `processual_api/admin_marketplace/persistence/protocols.py` — order, invoice
- `processual_api/admin_marketplace/persistence/repositories.py` — order, invoice
- `processual_api/admin_marketplace/persistence/unit_of_work.py` — order, invoice
- `processual_api/admin_marketplace/persistence/__init__.py` — order, invoice
- `processual_api/auth/delivery_repository.py` — order
- `processual_api/auth/mfa_repository.py` — order
- `processual_api/auth/registration_repository.py` — order
- `processual_api/auth/session_repository.py` — order
- `processual_api/billing/commercial_catalog_contracts.py` — checkout, purchase, order
- `processual_api/billing/commercial_currency_settlement_contracts.py` — checkout, purchase, order
- `processual_api/billing/commercial_entitlement_grant_posting_service.py` — checkout, order, invoice
- `processual_api/billing/commercial_entitlement_ledger_boundaries.py` — order
- `processual_api/billing/commercial_entitlement_ledger_repositories.py` — order
- `processual_api/billing/commercial_entitlement_policy_contracts.py` — purchase
- Additional matching files omitted from Markdown: 178

### quota

- Matching files: 145
- `processual_api/supervision_rbac.py` — quota
- `processual_api/admin_marketplace/contracts.py` — quota, entitlement
- `processual_api/admin_marketplace/models.py` — quota, entitlement
- `processual_api/admin_marketplace/__init__.py` — entitlement
- `processual_api/admin_marketplace/persistence/protocols.py` — entitlement
- `processual_api/admin_marketplace/persistence/repositories.py` — entitlement
- `processual_api/admin_marketplace/persistence/unit_of_work.py` — entitlement
- `processual_api/admin_marketplace/persistence/__init__.py` — entitlement
- `processual_api/auth/security.py` — quota
- `processual_api/billing/commercial_adaptive_capacity_contracts.py` — quota
- `processual_api/billing/commercial_catalog_contracts.py` — quota, entitlement
- `processual_api/billing/commercial_entitlement_grant_posting_service.py` — entitlement, available_units
- `processual_api/billing/commercial_entitlement_ledger_boundaries.py` — entitlement, usage commit
- `processual_api/billing/commercial_entitlement_ledger_contracts.py` — entitlement, available_units
- `processual_api/billing/commercial_entitlement_ledger_in_memory.py` — entitlement, available_units
- `processual_api/billing/commercial_entitlement_ledger_models.py` — entitlement, available_units
- `processual_api/billing/commercial_entitlement_ledger_persistence_contracts.py` — entitlement, available_units
- `processual_api/billing/commercial_entitlement_ledger_repositories.py` — entitlement, available_units
- `processual_api/billing/commercial_entitlement_ledger_schema_contracts.py` — entitlement, available_units
- `processual_api/billing/commercial_entitlement_ledger_unit_of_work.py` — entitlement
- Additional matching files omitted from Markdown: 125

### admin_marketplace

- Matching files: 68
- `processual_api/admin_marketplace/audit_contracts.py` — admin_marketplace, platform_admin
- `processual_api/admin_marketplace/authority.py` — admin_marketplace, platform_admin
- `processual_api/admin_marketplace/contracts.py` — admin_marketplace
- `processual_api/admin_marketplace/errors.py` — admin marketplace
- `processual_api/admin_marketplace/models.py` — platform_admin
- `processual_api/admin_marketplace/__init__.py` — admin_marketplace
- `processual_api/admin_marketplace/persistence/errors.py` — admin marketplace
- `processual_api/admin_marketplace/persistence/integrity.py` — admin marketplace, admin_marketplace
- `processual_api/admin_marketplace/persistence/protocols.py` — admin_marketplace
- `processual_api/admin_marketplace/persistence/repositories.py` — admin_marketplace, commercial decision
- `processual_api/admin_marketplace/persistence/unit_of_work.py` — admin marketplace, admin_marketplace
- `processual_api/admin_marketplace/persistence/__init__.py` — admin_marketplace
- `processual_api/auth/admin_recovery_email_repository.py` — platform_admin
- `processual_api/auth/admin_recovery_email_service.py` — platform_admin
- `processual_api/auth/delivery_operations_router.py` — platform_admin
- `processual_api/auth/models.py` — platform_admin
- `processual_api/auth/platform_admin_bootstrap.py` — platform_admin
- `processual_api/auth/platform_admin_bootstrap_repository.py` — platform_admin
- `processual_api/auth/platform_admin_bootstrap_service.py` — platform_admin
- `processual_api/auth/platform_supervisor_repository.py` — platform_admin
- Additional matching files omitted from Markdown: 48

### tunisia_payment

- Matching files: 21
- `processual_api/admin_marketplace/contracts.py` — country_code
- `processual_api/admin_marketplace/models.py` — country_code
- `processual_api/billing/commercial_currency_settlement_contracts.py` — tunisia
- `processual_api/billing/commercial_settings_top_up_checkout_contracts.py` — tunisia, tunisian, country == "TN"
- `processual_api/billing/commercial_top_up_models.py` — tunisia
- `processual_api/billing/unit_cost_assumptions.py` — tunisia
- `processual_api/static/js/admin_api_keys.js` — tunisia
- `alembic/versions/20260727_0011_admin_marketplace_persistence.py` — country_code
- `alembic/versions/20260729_0013_commercial_top_up_persistence.py` — tunisia
- `alembic/versions/20260729_0014_commercial_usd_tnd_settlement.py` — tunisia
- `tests/test_admin_api_key_external_usage_regression.py` — tunisia
- `tests/test_admin_api_key_lifecycle_regression.py` — tunisia
- `tests/test_admin_marketplace_channel_policy_r1.py` — tunisia, tunisian, country_code
- `tests/test_commercial_currency_settlement_contracts_boundaries_group2.py` — tunisia
- `tests/test_commercial_currency_settlement_contracts_group2.py` — tunisia
- `tests/test_commercial_currency_settlement_migration_group2.py` — tunisia
- `tests/test_commercial_currency_settlement_models_group2.py` — tunisia
- `tests/test_commercial_settings_top_up_checkout_contracts_boundaries_group2.py` — tunisia
- `tests/test_commercial_settings_top_up_checkout_contracts_group2.py` — tunisia, tunisian, country="TN"
- `tests/test_unit_cost_assumptions.py` — tunisia
- Additional matching files omitted from Markdown: 1

### lemon_squeezy

- Matching files: 54
- `processual_api/admin_marketplace/contracts.py` — lemon_squeezy
- `processual_api/admin_marketplace/models.py` — lemon_squeezy
- `processual_api/billing/commercial_currency_settlement_contracts.py` — lemon squeezy, lemon_squeezy
- `processual_api/billing/commercial_settings_top_up_checkout_contracts.py` — lemon_squeezy
- `processual_api/billing/commercial_top_up_models.py` — lemon_squeezy
- `processual_api/billing/router.py` — lemon squeezy, lemonsqueezy, lemon_squeezy
- `processual_api/billing/subscription_catalog.py` — lemon squeezy
- `processual_api/billing/unit_cost_assumptions.py` — lemon_squeezy
- `processual_api/billing/__init__.py` — lemon squeezy
- `processual_api/static/js/admin_api_keys.js` — lemon squeezy
- `alembic/versions/20260727_0011_admin_marketplace_persistence.py` — lemon_squeezy
- `alembic/versions/20260729_0013_commercial_top_up_persistence.py` — lemon_squeezy
- `alembic/versions/20260729_0014_commercial_usd_tnd_settlement.py` — lemon_squeezy
- `tests/test_admin_api_key_profiles_regression.py` — lemon squeezy, lemonsqueezy
- `tests/test_admin_marketplace_audit_contracts_r1.py` — lemon_squeezy
- `tests/test_admin_marketplace_channel_policy_r1.py` — lemon_squeezy
- `tests/test_admin_marketplace_migration_r2.py` — lemon_squeezy
- `tests/test_admin_marketplace_models_r2.py` — lemon_squeezy
- `tests/test_admin_marketplace_payment_repositories_r3.py` — lemon_squeezy
- `tests/test_billing_pricing_catalog_route.py` — lemonsqueezy
- Additional matching files omitted from Markdown: 34

### ui_ux

- Matching files: 56
- `processual_api/billing/commercial_settings_top_up_checkout_contracts.py` — loading
- `processual_api/billing/commercial_settings_top_up_ui_contracts.py` — loading
- `processual_api/billing/commercial_ui_contracts.py` — loading
- `processual_api/integrations/outbound_allowlist_tls_readiness.py` — loading
- `processual_api/static/admin.html` — loading, aria-
- `processual_api/static/index.html` — loading, aria-
- `processual_api/static/login.html` — aria-
- `processual_api/static/pricing.html` — loading, aria-
- `processual_api/static/splash.html` — loading
- `processual_api/static/css/console.css` — empty state, responsive
- `processual_api/static/js/admin_actions.js` — loading
- `processual_api/static/js/admin_api_keys.js` — loading, aria-
- `processual_api/static/js/admin_api_key_summary.js` — loading
- `processual_api/static/js/admin_client_requests.js` — loading, empty state, aria-
- `processual_api/static/js/admin_dashboard.js` — loading
- `processual_api/static/js/admin_home_layout.js` — loading
- `processual_api/static/js/admin_integration_center_18.js` — loading
- `processual_api/static/js/admin_integration_pilot_controls_13b.js` — loading, aria-
- `processual_api/static/js/admin_integration_readiness.js` — loading, aria-
- `processual_api/static/js/admin_layout_cleanup.js` — loading
- Additional matching files omitted from Markdown: 36

### runtime_flags

- Matching files: 218
- `processual_api/main.py` — enabled
- `processual_api/settings.py` — enabled
- `processual_api/auth/account_recovery_external_revocation.py` — enabled
- `processual_api/auth/mfa_contracts.py` — enabled
- `processual_api/auth/mfa_router.py` — enabled
- `processual_api/auth/mfa_service.py` — enabled
- `processual_api/auth/registration_contracts.py` — enabled
- `processual_api/billing/commercial_adaptive_capacity_contracts.py` — enabled
- `processual_api/billing/commercial_catalog_contracts.py` — enabled
- `processual_api/billing/commercial_currency_settlement_contracts.py` — enabled
- `processual_api/billing/commercial_entitlement_grant_posting_service.py` — enabled, runtime_wiring, commercial_activation
- `processual_api/billing/commercial_entitlement_ledger_boundaries.py` — enabled
- `processual_api/billing/commercial_entitlement_ledger_contracts.py` — enabled
- `processual_api/billing/commercial_entitlement_ledger_in_memory.py` — enabled
- `processual_api/billing/commercial_entitlement_ledger_models.py` — enabled
- `processual_api/billing/commercial_entitlement_ledger_persistence_contracts.py` — enabled
- `processual_api/billing/commercial_entitlement_ledger_repositories.py` — enabled
- `processual_api/billing/commercial_entitlement_ledger_schema_contracts.py` — enabled
- `processual_api/billing/commercial_entitlement_ledger_unit_of_work.py` — enabled
- `processual_api/billing/commercial_entitlement_policy_contracts.py` — enabled
- Additional matching files omitted from Markdown: 198


## Boundary evidence

- platform_admin_exclusive: **FOUND**
- delegated_supervisor_denial: **FOUND**
- tunisia_optional_local_path: **FOUND**
- lemon_squeezy_alternative: **FOUND**
- checkout_fail_closed: **FOUND**
- quota_fail_closed: **FOUND**
- runtime_fail_closed: **FOUND**
- byok_only: **FOUND**

## Consolidated implementation plan

### 1. Commercial authority and durable records

Scope:
- Subscription lifecycle authority
- Order, invoice, payment-evidence, and settlement references
- Activation and renewal decisions
- Fail-closed state transitions
- Audit trail and idempotency

Acceptance:
- No grant without approved commercial authority
- No duplicate activation or renewal
- No implicit checkout enablement
- PostgreSQL transaction coverage

### 2. Checkout and channel orchestration

Scope:
- General Lemon Squeezy path
- Optional Tunisian local-payment path
- Address and eligibility policy
- Customer choice preservation
- Provider webhook and evidence boundaries

Acceptance:
- TN path only for eligible Tunisian addresses
- Lemon Squeezy remains available
- No Admin Marketplace registration flow
- No activation from unverified payment

### 3. Quota and consumption integration

Scope:
- Entitlement availability checks
- Reserve, commit, release, and reversal bridge
- Dynamic plan limits and concurrency
- Rollover-safe consumption
- Observe-only shadow metrics before enforcement

Acceptance:
- Ledger remains source of truth
- CAS protects concurrent balance updates
- No confiscatory rollover cap
- Enforcement remains disabled until staging gate

### 4. Admin Marketplace controls

Scope:
- Platform-admin-only commercial console
- Explicit delegated-supervisor denial
- Payment verification and activation decisions
- Channel eligibility and audit
- Fail-closed unknown actions

Acceptance:
- Exclusive platform_admin authorization
- Explicit rejection tests
- No customer registration or subscription ownership
- Complete commercial audit context

### 5. Integrated UI/UX and observe-only runtime

Scope:
- Reuse current design system
- Loading, error, empty, success, and pending states
- Accessibility and responsive behavior
- Clear channel choice and pricing summary
- Observe-only runtime telemetry

Acceptance:
- No temporary UI
- No ambiguous payment or activation state
- Keyboard and screen-reader coverage
- Runtime writes and enforcement remain disabled


## Delivery structure

The implementation should be delivered through a small number of coherent commits inside one branch and one package review:

1. Durable commercial authority and transaction contracts.
2. Channel and checkout orchestration with Tunisian eligibility.
3. Quota-consumption and Admin Marketplace integration.
4. Integrated UI/UX and observe-only runtime qualification.
5. One combined PostgreSQL, security, regression, and staging gate.

## Activation rule

No production or staging enforcement flag may be enabled merely because this discovery is complete. Activation requires the final combined package gate and explicit approval.