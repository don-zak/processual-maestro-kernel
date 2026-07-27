# Processual Maestro Kernel — Master Remaining Execution Roadmap

## Document authority

This file is the canonical and mandatory source for the remaining execution
plan of Processual Maestro Kernel.

Every transition report must include the complete current contents of this
file, or an exact clearly marked snapshot of it.

No transition report may omit later phases merely because the current branch
implements an earlier phase.

## Governing execution order

The approved order is:

1. Complete the remaining authentication program.
2. Build the dedicated Admin Marketplace inside the platform administrator area.
3. Implement direct sales inside Tunisia independently from Lemon Squeezy.
4. Block Lemon Squeezy checkout for customers governed as Tunisian customers.
5. Define and enforce plans, entitlements, quotas and usage accounting.
6. Determine and approve prices and commercial policies.
7. Reconcile the public and private repositories.
8. Perform general product packaging.
9. Qualify a real staging environment.
10. Build and approve a release candidate.
11. Execute a controlled production pilot.
12. Proceed to general availability only after all release gates pass.

The product must not skip directly from authentication work to packaging or
production preparation.

---

# Phase A — Remaining authentication program

## AUTH-R9B — Production account-recovery delivery lifecycle

Goal:

Complete and qualify the production delivery lifecycle used by secure account
recovery.

Required scope:

- Reuse the encrypted authentication delivery outbox.
- Keep raw recovery tokens out of PostgreSQL, logs and audit records.
- Require an authenticated production delivery provider configuration.
- Validate provider and public URLs as fixed HTTPS authorities.
- Preserve stable provider idempotency keys.
- Perform provider I/O outside database transactions.
- Use bounded lease claiming.
- Use capped exponential backoff with deterministic jitter.
- Support retry, dead-letter and stale-worker protection.
- Sanitize provider error codes.
- Prohibit recipient addresses, tokens, URLs containing tokens, ciphertext,
  bearer credentials and provider bodies from logs.
- Preserve default-deny behavior when runtime authority is unavailable.
- Cover timeout, connection, malformed response, rejected request and
  crash-after-send behavior.
- Add real PostgreSQL delivery integration proof.
- Add production-like provider contract proof without exposing secrets.

Exit gate:

- Production account-recovery delivery lifecycle tests pass.
- Retry and dead-letter evidence is captured.
- Idempotency behavior is proven.
- No-secret logging proof passes.
- Runtime fails closed when required delivery authority is missing.

## AUTH-R9C — HTTP end-to-end recovery proof

Required scope:

- Real PostgreSQL.
- Real Redis.
- Start recovery request.
- Capture and decrypt test delivery only inside an isolated proof.
- Verify the recovery token.
- Issue a separate completion token.
- Complete password replacement.
- Reject old password.
- Accept new password.
- Reject verification replay.
- Reject completion replay.
- Verify rate limits and generic enumeration-safe responses.
- Verify security and no-store headers.
- Verify that completion creates no session, access token, refresh token,
  API key or platform authority.
- Verify revocation of:
  - authenticated sessions;
  - refresh tokens;
  - action tokens;
  - MFA factors;
  - MFA recovery codes;
  - supervisor session keys;
  - client API keys.
- Verify cleanup of isolated test data.

Exit gate:

- Full HTTP round trip passes against PostgreSQL and Redis.
- Replay denial passes.
- Old/new password behavior passes.
- Authority revocation passes.
- No automatic authentication authority is issued.

## AUTH-R9D — Operational recovery security

Required scope:

- Recovery lifecycle audit events.
- Password-change notification.
- MFA re-enrollment notification.
- Suspicious recovery-attempt detection.
- Safe support diagnostics.
- High-authority account handling.
- First platform administrator lockout prevention.
- Security event correlation without recording secrets.
- Operational metrics and alert definitions.
- Provider failure and dead-letter operational procedures.

Exit gate:

- Operational audit contract passes.
- Security notifications are qualified.
- Diagnostics expose no sensitive material.
- Administrator recovery remains fail-closed and recoverable.

## AUTH-R10 — Final authentication hardening and closure

Required scope:

- Authentication migration upgrade/downgrade round trips.
- Concurrent registration, login, refresh, MFA and recovery race tests.
- Secret and key rotation.
- PostgreSQL backup and restore proof.
- Redis dependency and recovery behavior.
- Browser end-to-end tests.
- Accessibility and Arabic/English direction tests for authentication UI.
- Full authentication regression.
- Full repository regression.
- Coverage gate.
- Ruff.
- Flake8.
- Mypy.
- Bandit.
- pip-audit.
- Build and package validation.
- Secret scan.
- Git diff check.
- Exact-scope verification.
- Final AUTH evidence bundle.

AUTH closure condition:

AuthenticationProgramComplete=True
PlatformAdministratorLockoutPrevented=True
ProductionAuthProofPassed=True

---

# Phase B — Admin Marketplace

The Admin Marketplace is a dedicated page within the first platform
administrator space.

Canonical route target:

/admin/marketplace

The marketplace is not a small settings panel and must not be mixed with
customer-facing checkout pages.

## ADMIN-MARKET-R1 — Domain and authority contracts

- Define offers, plans, subscriptions, trials, orders, payments, invoices,
  activations and commercial decisions.
- Define exclusive super-administrator permissions and explicit delegated-
  supervisor denial.
- Enforce default deny.
- Prohibit wildcard commercial authority.
- Restrict Admin Marketplace access and all commercial decisions exclusively to
  the first platform administrator acting as super administrator.
- Explicitly deny delegated supervisors, ordinary administrators, customers,
  institutions and unauthenticated actors.
- Require step-up MFA for sensitive commercial operations.
- Define immutable audit records.

## ADMIN-MARKET-R2 — Persistence and migrations

- Add commercial offer tables.
- Add customer and institution sales records.
- Add order and payment-verification records.
- Add subscription and entitlement records.
- Add activation history.
- Add trial lifecycle.
- Add commercial audit linkage.
- Provide reversible Alembic migrations.

## ADMIN-MARKET-R3 — Tunisia sales-channel governance and customer choice

Approved policy:

- The Admin Marketplace is a private page available only to the first
  platform administrator acting as super administrator, for managing and
  selling software usage rights.
- Maestro direct sales must be available for supported Tunisian sales.
- Eligible Tunisian customers and institutions may also choose Lemon Squeezy
  when that channel is commercially, legally and operationally available.
- Tunisian residency, organization country or billing country must not
  automatically prohibit Lemon Squeezy checkout.
- Customers retain freedom to choose among the sales channels for which they
  are eligible.
- Channel eligibility must be based on documented commercial, legal, provider,
  security and operational rules.
- Country governance must not depend only on IP address.
- Relevant signals may include authoritative customer or institution country,
  billing address, verified organization data, telephone-country signal, tax
  identity where applicable and administrator review.
- Ambiguous or conflicting evidence must fail closed for automatic activation
  and require administrator review, without silently forcing a different sales
  channel.
- A selected channel must not be changed after checkout or order initiation
  without customer consent or a documented, auditable restriction.
- Every channel-eligibility, restriction, customer-selection and administrator-
  override decision must be recorded in the immutable commercial audit trail.

Required decision examples:

Country=TN
MaestroDirectAllowed=True
LemonSqueezyCheckoutAllowed=True
CustomerChannelChoiceAllowed=True
AdminReviewRequired=False

Country=TN
MaestroDirectAllowed=True
LemonSqueezyCheckoutAllowed=False
CustomerChannelChoiceAllowed=False
AdminReviewRequired=True
RestrictionReason=DOCUMENTED_PROVIDER_LEGAL_SECURITY_OR_OPERATIONAL_RESTRICTION

EligibleCountryOutsideTunisia=True
MaestroDirectAllowed=POLICY_DEPENDENT
LemonSqueezyCheckoutAllowed=True
CustomerChannelChoiceAllowed=True
AdminReviewRequired=False

## ADMIN-MARKET-R4 — Offer management

- Create, revise, publish, suspend and retire offers.
- Support Tunisian dinar and approved international currencies.
- Bind every offer to entitlements and quotas.
- Support public and customer-specific offers.
- Support effective dates and expiry.
- Prevent retroactive silent changes to active subscriptions.

## ADMIN-MARKET-R5 — Direct Tunisian order workflow

- Create direct-sale order.
- Record customer or institution identity.
- Record payment method and payment reference.
- Upload or reference evidence without exposing it publicly.
- Require payment verification.
- Require terms acceptance.
- Require appropriate administrator approval.
- Activate only after all gates pass.
- Preserve a complete decision history.

Potential local methods may include bank transfer, invoice, purchase order or
another later-approved Tunisian payment integration. No method is considered
production-approved until separately qualified.

## ADMIN-MARKET-R6 — Trial management

- Free or paid trial policy.
- Trial duration.
- Trial quotas.
- Sandbox-only versus limited operational access.
- Connector permissions.
- Supervisor approval.
- Extension, suspension, conversion and expiry.
- No production authority by implication.

## ADMIN-MARKET-R7 — Subscription lifecycle

- Activation.
- Renewal.
- Upgrade.
- Downgrade.
- Suspension.
- Cancellation.
- Expiry.
- Refund decision under the approved operational-outcome policy.
- Immutable lifecycle history.

## ADMIN-MARKET-R8 — Lemon Squeezy boundary

- Server-side checkout authorization.
- Server-side enforcement of documented channel-eligibility and restriction
  decisions.
- Variant mapping only for approved offers and eligible customers or
  institutions.
- Webhook authenticity and replay prevention.
- Idempotent order reconciliation.
- No activation from an unverified webhook.
- Channel-eligibility and customer-selection revalidation before activation.
- Safe handling of refunds, disputes and subscription changes.

## ADMIN-MARKET-R9 — Administrator user interface

Dedicated super-administrator-only page containing:

- Offer management.
- Customer and institution sales.
- Pending payment verification.
- Trials.
- Active subscriptions.
- Expiring subscriptions.
- Suspended accounts.
- Usage versus quotas.
- Revenue and commercial summaries.
- Audit trail.
- Maestro Direct and Lemon Squeezy eligibility, selection and restriction
  indicators.

The page must follow the existing Maestro UI system, responsive behavior,
accessibility rules and Arabic/English direction handling.

## ADMIN-MARKET-R10 — Commercial security and closure

- Exclusive super-administrator permission, delegated-supervisor denial and
  step-up MFA tests.
- Payment-evidence access controls.
- Webhook security tests.
- Channel-eligibility, customer-choice and restriction-bypass tests.
- Concurrent activation tests.
- Idempotency and replay tests.
- Browser tests.
- Full regression.
- Final commercial evidence bundle.

---

# Phase C — Quotas and entitlements

## QUOTAS-R1 — Entitlement catalog

Candidate controlled dimensions:

- users;
- organizations;
- agents;
- concurrent agents;
- tasks per day;
- tasks per month;
- compute or token budget;
- storage;
- API requests;
- connectors;
- sandbox hours;
- production runs;
- reports;
- retention days;
- support level;
- active cases;
- scheduled jobs;
- external operations;
- write operations;
- restricted operations;
- supervisor approvals;
- qualification keys;
- sandbox keys.

## QUOTAS-R2 — Usage authority

Every quota must define:

- limit;
- reset period;
- current usage;
- remaining usage;
- reservation behavior;
- release behavior;
- overage policy;
- notification thresholds;
- hard denial versus administrator approval.

## QUOTAS-R3 — Enforcement

- API enforcement.
- Background-task enforcement.
- Agent concurrency enforcement.
- Connector-operation enforcement.
- Sandbox enforcement.
- Subscription-state enforcement.
- Atomic usage accounting.
- Race and replay protection.

## QUOTAS-R4 — Visibility and qualification

- Customer usage pages.
- Administrator usage pages.
- Threshold warnings.
- Usage export.
- Reconciliation tests.
- Load and concurrency tests.
- Final quota evidence bundle.

---

# Phase D — Pricing

## PRICING-R1 — Cost model

Include:

- hosting;
- databases;
- storage;
- monitoring;
- support;
- onboarding;
- connectors;
- operational risk;
- payment fees;
- taxes where applicable;
- margin;
- BYOK policy;
- excluded AI-provider costs.

## PRICING-R2 — Offer families

Current planned families:

- Pilot Starter;
- Pilot Pro;
- Institution Trial;
- Institution;
- Enterprise;
- Custom/Telecom.

Enterprise and Custom/Telecom require:

SupervisorReviewRequired=True
PriceManuallyApproved=True
ActivationAfterContract=True

## PRICING-R3 — Approval and versioning

- Approved currency.
- Approved price.
- Effective date.
- Price version.
- Tax treatment.
- Discount authority.
- Renewal behavior.
- Customer-specific negotiated terms.
- No silent modification of active contracts.

## PRICING-R4 — Final commercial qualification

- Price-to-quota consistency.
- Tunisia/direct price display.
- International Lemon Squeezy mapping.
- Invoice and order consistency.
- Refund-policy visibility.
- Browser and API tests.
- Commercial approval evidence.

No production checkout may be enabled before PRICING-R4 closes.

---

# Phase E — Public/private repository reconciliation

This phase occurs after AUTH, Admin Marketplace, quotas and pricing are
functionally complete.

Required work:

- Compare shared trees.
- Preserve private-only integrations.
- Confirm public build excludes private modules and tests.
- Port the latest approved public core into the private baseline.
- Run public and private full suites.
- Run public-exclusion tests.
- Build public and private images.
- Validate shared migrations.
- Produce exact drift and compatibility evidence.

---

# Phase F — General packaging

Required work:

- Remove temporary and obsolete files.
- Normalize product terminology.
- Complete README and operator documentation.
- Complete administrator documentation.
- Complete customer documentation.
- Provide safe configuration templates.
- Finalize migrations.
- Review feature flags.
- Build packages and Docker images.
- Generate SBOM.
- Generate dependency and license inventory.
- Run secret and vulnerability scans.
- Assign release version.
- Prepare changelog and release notes.
- Prepare backup, restore, rollback and incident-response manuals.

---

# Phase G — Real staging qualification

Synthetic CI rehearsal is not real staging qualification.

Required work:

- Real staging environment.
- Immutable image digest.
- Real secret authority.
- Migration rehearsal.
- Backup and restore.
- Rollback.
- Health and readiness.
- Metrics and alerts.
- External provider integration.
- Browser end-to-end.
- Load and endurance tests.
- Security review.
- Named human approvals.
- Externally verifiable approval evidence.
- Signed Go/No-Go decision.

---

# Phase H — Release candidate and launch

## Release candidate

- Freeze exact source heads.
- Freeze exact image digests.
- Freeze migrations.
- Freeze pricing and quotas.
- Freeze documentation.
- Complete release evidence bundle.
- No unresolved critical or high defects.
- Formal Go/No-Go.

## Controlled production pilot

- Limited customers.
- Limited quotas.
- Enhanced monitoring.
- Fast rollback authority.
- Incident-response readiness.
- Daily operational review.
- Explicit expansion decision.

## General availability

General availability is allowed only after:

- authentication closure;
- Admin Marketplace closure;
- quota closure;
- pricing closure;
- repository reconciliation;
- packaging;
- real staging;
- release candidate approval;
- successful controlled pilot.

---

# Mandatory transition-report rule

Every transition report must include:

1. Repository and workspace.
2. Current branch and exact HEAD.
3. Parent/base commit.
4. Working-tree and staged-file state.
5. Exact changed paths.
6. Completed work.
7. Tests and validation evidence.
8. Known failures and unresolved risks.
9. Current phase and precise next task.
10. The full remaining roadmap from this file.
11. Explicit statements for:
    - PushPerformed;
    - PullRequestOpened;
    - MergePerformed;
    - ProductionAuthorityGranted;
    - RealStagingQualified.
12. Commands and paths required to resume safely.

No transition report may claim production readiness merely because a synthetic
or ephemeral CI rehearsal passed.