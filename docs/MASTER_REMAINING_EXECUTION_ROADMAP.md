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
4. Enforce the approved Tunisia sales-channel governance policy: eligible Tunisian customers may choose Lemon Squeezy when that channel is commercially, legally, operationally and securely available; Tunisian country status alone must not block Lemon Squeezy checkout.
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
