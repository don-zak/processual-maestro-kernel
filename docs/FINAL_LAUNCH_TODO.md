# Final Launch TODO

This file is the authoritative pre-launch checklist for Processual Maestro. A task is not complete because code exists; it is complete only when its acceptance evidence is recorded and the relevant CI/runtime qualification is green.

## Qualification Phase Policy

Two qualification phases are intentionally separated:

1. **Current Closed Qualification** — the current Render/External Evaluation environment is closed and operator-controlled. Continue the already-qualified recovery contract without escalating recovery requirements. The purpose is to prove the current delivery/runtime chain, password reset, revocation behavior, MFA reenrollment, Admin authority restoration, and External Evaluation E2E.
2. **Final Launch Qualification** — before public/final launch, apply the complete Account Recovery Hardening contract below for customer and Platform Admin flows. This includes a second independent factor, verified phone/OTP where selected, stronger Admin policy, downgrade protection, abuse controls, and the corresponding UI/operator behavior.

The final-launch hardening requirements below are **not a blocker for completing the current closed-environment qualification**, but they remain mandatory before the final release gate can be closed.

## P0 — Final Launch Account Recovery Hardening

> Scope: **Final Launch Qualification only.** Do not interrupt or replace the current closed-environment recovery E2E with these requirements while the present qualification sequence is in progress.

- [ ] Require a second independent recovery factor before password reset completion for final-launch customer recovery.
  - Preferred launch contract: verified recovery email link/token **plus** one additional factor that was enrolled before the recovery attempt.
  - Supported second factors should be ordered by strength: passkey/security key or recovery code first; verified phone OTP may be supported as an additional fallback.
  - SMS/phone OTP must never become the sole recovery authority because of SIM-swap/number-reassignment risk.
  - The existing password must **not** be mandatory in the Lost Access flow; if the user still knows the current password, use the normal password-change/step-up flow instead of account recovery.
- [ ] Define a separate stronger Platform Admin recovery policy for final launch.
  - Require the strongest qualified enrolled second factor available under policy.
  - Fail closed when the required privileged recovery factor is unavailable.
  - Do not let customer recovery policy silently downgrade Platform Admin recovery authority.
  - Require explicit privileged reauthentication/MFA reenrollment before restoring Platform Admin authority.
- [ ] Add verified phone-number enrollment and change controls where phone recovery is enabled.
  - Phone number must be verified before it can be used for recovery.
  - Changing/removing a recovery phone requires authenticated step-up.
  - New/replaced phone factors must respect a cooling-off policy before becoming recovery authority.
  - Never expose whether a phone/email/account exists through recovery responses.
- [ ] Add short-lived single-use OTP confirmation for phone recovery.
  - Bind OTP to recovery request + account + intended action.
  - Enforce expiry, attempt limits, resend cooldown, replay protection, and rate limiting.
  - Store only a one-way verifier; never log raw OTP values.
- [ ] Add recovery factor downgrade protection.
  - An attacker controlling one factor must not be able to replace the second factor and immediately use it to recover the account.
  - Introduce cooling-off and notification policy for sensitive recovery-factor changes.
- [ ] Preserve the post-recovery revocation contract.
  - Revoke refresh tokens, active sessions, action tokens, external supervisor/API keys, and existing MFA factors as required by policy.
  - Require MFA reenrollment before restoring privileged authority.
  - Do not auto-login or auto-restore Platform Admin authority after recovery.
- [ ] Complete customer-facing final-launch recovery UX.
  - Explain which verification step is required without revealing hidden account state.
  - Provide safe resend/expiry/error states.
  - Keep tokens/OTP values memory-only where applicable and out of logs/storage.
  - Do not expose internal authority, provider, or delivery details to the customer.
- [ ] Complete Platform Admin/operator recovery controls.
  - Provide safe status/audit visibility without exposing recovery tokens, OTP values, recipient secrets, or raw provider responses.
  - Record factor changes, recovery initiation/completion, revocations, and authority restoration as auditable security events.
  - Keep qualification/final readiness decision operator-controlled.
- [ ] Add full tests for recovery abuse cases.
  - Wrong/expired/replayed OTP.
  - Rate-limit exhaustion.
  - Factor replacement race.
  - SIM/phone fallback cannot bypass stronger configured factor policy.
  - No secret/token/OTP/recipient leakage in logs or evidence.
  - Concurrent recovery requests cannot create multiple valid completion authorities.

## P1 — Current Closed Recovery Delivery Qualification / Resend

> Scope: **Current Closed Qualification.** Continue the existing recovery contract as currently implemented. Do not add the final-launch second-factor requirement to this phase.

- [ ] Qualify the embedded delivery worker on the exact qualification SHA.
  - `AUTH_DELIVERY_EMBEDDED_WORKER_ENABLED=true`.
  - Poll interval explicitly configured.
  - Hosted logs show `identity_delivery_embedded_worker_started`.
  - Hosted logs show safe `identity_delivery_embedded_worker_batch_completed` evidence.
  - No secret-bearing exception text in logs.
- [ ] Perform one controlled Lost Access E2E qualification using the current recovery flow.
  - Recovery start returns 202 without account enumeration.
  - Outbox item is claimed once.
  - Resend accepts the delivery.
  - Delivery reaches the intended physical inbox.
  - Recovery link/token never appears in server request logs.
  - Password reset completes using the current closed-environment contract.
  - Old sessions/tokens/API keys are revoked.
  - MFA reenrollment completes.
  - Fresh login restores valid authority only after required current authentication factors.
- [ ] Qualify dead-letter/retry behavior and stale recovery-message finalization.
- [ ] Record this phase as **closed-environment qualification evidence only**; it must not be reused as proof that final-launch P0 recovery hardening is complete.

## P2 — External Evaluation Qualification

- [ ] Platform Admin authority endpoint returns authorized state only for a valid active Platform Admin session.
- [ ] Create External Evaluation grant.
- [ ] Issue Evaluation API key; raw key is shown once only and is never persisted/redisplayed/logged.
- [ ] External Evaluation API key requires no subscription, registration, or commercial quota authority; all allowed tasks, bindings, endpoints, expiry, evaluation type, and admitted-execution quota are derived from the authoritative grant.
- [ ] Grant explicitly classifies the key as CRM or Integration and applies the corresponding fixed evaluation quota policy rather than a client/UI-selected commercial plan.
- [ ] Generate a customer handoff text beside the one-time API key containing only safe technical/operational details needed to complete the evaluation: portal/base URL, header name, grant/key identifiers or prefix, evaluation type, expiry, quota, allowed tasks/bindings/endpoints, idempotency guidance, production-disabled statement, and support/next-step guidance. It must contain no additional secret material beyond the separately displayed one-time key.
- [ ] Confirm key delivery and customer receipt acknowledgment.
- [ ] Customer runtime dashboard displays grant/key safe metadata, credential state, CRM/Integration type, quota limit, admitted usage, remaining quota, authorized scope, current execution stage, latest safe receipt/evidence, and `production_execution=false` without Admin access.
- [ ] Customer execution UX clearly communicates the progression `admitted -> executing -> succeeded/failed -> evidence persisted` and whether the operation consumed `+1` or was an idempotent replay at `+0`.
- [ ] Provide the customer a safe execution report/receipt for their own evaluation key while preserving the Admin copy and keeping the final qualification decision operator-controlled.
- [ ] Prove quota semantics.
  - CRM quota = 100.
  - Integration quota = 200.
  - Authentication/status/replay consume +0.
  - First newly admitted execution consumes +1.
  - Downstream failure after admission still consumes +1.
  - Exhaustion/concurrency proven by automated tests/DB qualification rather than burning the live quota.
- [ ] Prove idempotent replay returns durable prior result at +0 quota.
- [ ] Execute through the qualified external sandbox and persist safe evidence.
- [ ] Prove evidence excludes raw canonical input, secrets, raw provider responses, and raw Evaluation key material.
- [ ] Prove individual key revocation is immediate and does not revoke sibling keys.
- [ ] Prove grant-wide revocation cascades to active linked keys.
- [ ] Deliver final Admin audit summary with `report_type=external_evaluation_final_summary` and `qualification_decision=operator_required`.

## P3 — Render / Runtime Readiness

- [ ] Exact release SHA is Live on the authority service.
- [ ] `/health/live` is continuously healthy after rollout.
- [ ] `/health/ready` is explicitly qualified and documented; do not infer readiness from liveness.
- [ ] Remove startup fragility where long migrations/bootstrap can delay port binding enough to trigger Render port-scan timeout.
  - Prefer a safe pre-deploy migration/bootstrap phase or another deployment contract that cannot block web port binding beyond platform limits.
  - Preserve fail-closed authority semantics.
- [ ] Resolve production hardening warnings for `POSTGRES_PASSWORD`, `REDIS_PASSWORD`, and `GRAFANA_ADMIN_PASSWORD` or document why the specific variables are non-authoritative in this deployment contract.
- [ ] Make the Render blueprint reproduce the real delivery runtime configuration instead of relying on manual drift.
  - Delivery key-ring/current key version declarations.
  - Provider kind.
  - Resend sender/base URL declarations.
  - Embedded-worker enable/poll settings.
  - Secret values remain secret-managed and never committed.

## P4 — Authentication / Session / MFA

- [ ] Re-qualify session refresh with HttpOnly refresh cookie + double-submit CSRF.
- [ ] Confirm `mfa_required` always fails closed and cannot be bypassed by refresh/recovery flows.
- [ ] Confirm browser legacy credential aliases remain purged and no long-lived bearer authority is stored in localStorage.
- [ ] Confirm Platform Admin privileged actions require the intended step-up policy.
- [ ] Add explicit negative E2E tests for stale/revoked sessions after password reset, recovery, MFA changes, and privilege changes.

## P5 — Billing / External Providers

- [ ] Qualify LemonSqueezy checkout against the final server-side plan/variant catalog in non-production/live-safe mode.
- [ ] Confirm arbitrary client-controlled variant IDs cannot be submitted.
- [ ] Confirm provider errors remain generic and never leak API keys/provider payloads.
- [ ] Decide whether Gemini is launch-critical.
  - If yes: perform a live non-production Gemini provider smoke test using server-side credentials only.
  - If no: explicitly mark Gemini live smoke as post-launch/non-blocking.
- [ ] Decide whether Google end-user OAuth (Drive/Gmail/etc.) is required at launch.
  - If required: implement and qualify it as a separate connector/auth track.
  - If not required: state explicitly that it is outside launch scope.

## P6 — Evaluation Sandbox Boundary

- [ ] Deploy the evaluation-owned sandbox from the minimal Docker context.
- [ ] Pin and record the immutable sandbox revision used by qualification.
- [ ] Prove only the intended safe endpoints/methods are exposed.
- [ ] Prove sandbox receives no authority credentials and cannot issue grants, keys, quota, admission, or final verdicts.
- [ ] Prove real Maestro admission → sandbox execution → receipt/evidence path end-to-end.

## P7 — Data / Authority Integrity

- [ ] Re-qualify PostgreSQL row-locking and quota concurrency behavior on the release code.
- [ ] Re-qualify replay-before-consumption and duplicate-admission protection.
- [ ] Replace the bounded latest-100 execution lookup with a direct/indexed lookup for durable execution identifiers before it becomes an operational limit.
- [ ] Review retention/expiry policies for recovery requests, delivery outbox rows, evaluation executions, evidence, and audit summaries.
- [ ] Confirm database backup/restore expectations for launch and document an operator recovery procedure.

## P8 — Observability / Audit

- [ ] Ensure worker lifecycle/dispatch counters are visible in hosted logs without exposing secrets, recipients, tokens, raw inputs, or provider responses.
- [ ] Add alerts or operator checks for delivery retry/dead-letter growth, readiness failure, authority-service failure, and DB/Redis connectivity degradation.
- [ ] Ensure final External Evaluation audit copy reaches Admin and is immutable/durable enough for operator review.
- [ ] Review all exception logging paths for raw `str(exc)` leakage where exceptions could ever contain sensitive data; prefer reason codes/exception type where appropriate.

## P9 — Deployment / Repository Hygiene

- [ ] Remove duplicate Grafana dashboard volume mount in `docker-compose.yml`.
- [ ] Update `.env.production.example` and deployment documentation to match the final delivery/worker configuration contract without committing secrets.
- [ ] Update PR #210 description/current qualified head before final review.
- [ ] Keep PR #211 isolated until #210 qualification is complete; do not merge/rebase it casually.
- [ ] Keep public `main` untouched until explicit merge authorization and final launch gate review.
- [ ] Perform a full Admin-space and whole-program UI/UX value review before final release. Every API-key/Admin control, metric, note, example, table, badge, and action must have a real operational purpose, derive from authoritative state where applicable, and avoid demo/placeholder/duplicated or misleading content.
- [ ] Perform a deliberate repository and static-asset deprecation sweep after the functional/UI review: identify files, routes, scripts, styles, pages, compatibility bridges, tests, deployment fragments, and documentation that were replaced, superseded, or are no longer loaded/referenced. Prove non-use with imports/routes/asset references/tests before deletion; then remove confirmed dead artifacts rather than leaving parallel legacy paths indefinitely.
- [ ] Re-run a second dead-code/dead-asset sweep after deletions to catch transitive leftovers, duplicate implementations, stale comments/markers, obsolete compatibility aliases, and unused dependencies. Record what was removed and why, and keep anything uncertain until its consumers are proven absent.

## P10 — Private Overlay / Supply Chain

- [ ] After public head is fully qualified, sync the shared allowlisted layer into the private repository without overwriting protected private paths.
- [ ] Prove zero diff for protected private overlay paths before committing sync.
- [ ] Run public-compatible tests plus private CGT/security suites.
- [ ] Qualify private CI and resolve runner/infrastructure failures separately from code failures.
- [ ] Build private production artifact/container from the qualified private source.
- [ ] Add/verify SBOM, provenance, signing, digest pinning, restricted image pull permissions, restricted runtime identity, controlled egress, and safe logging.
- [ ] Do not merge private PR #56 without explicit authorization.

## P11 — Security Review Before Launch

- [ ] Threat-model account recovery, admin authority, Evaluation key issuance/revocation, quota authority, provider delivery, billing, and sandbox boundary.
- [ ] Re-run dependency/security scans on the exact release SHA.
- [ ] Verify no production secrets exist in repository history/current diffs/artifacts/logs.
- [ ] Verify CORS, CSRF, cookie flags, security headers, rate limits, and privileged endpoint authorization on the deployed release.
- [ ] Perform a targeted abuse-case review for account enumeration, credential stuffing, recovery flooding, OTP brute force, replay, privilege escalation, and quota bypass.

## P12 — Final Release Gate

- [ ] Freeze one release candidate SHA; all qualification evidence must refer to that exact SHA.
- [ ] All required GitHub CI/security gates green on that SHA.
- [ ] Authority service Live on that SHA.
- [ ] Required health/readiness checks green.
- [ ] Current closed-environment recovery qualification evidence is complete.
- [ ] Final-launch Account Recovery P0 is implemented and qualified for customer and Platform Admin flows.
- [ ] Final-launch Account Recovery E2E is green with second-factor hardening.
- [ ] External Evaluation E2E green.
- [ ] Required billing/provider smoke tests green or explicitly waived as non-launch scope.
- [ ] Private overlay/supply-chain qualification green if private production components are part of launch.
- [ ] No unresolved launch-blocking P0/P1 issues.
- [ ] Final audit/report reviewed by a human operator; system does not auto-declare production readiness.
- [ ] Merge/release only after explicit operator authorization.

## Non-Negotiable Authority Invariant

`Policy / Authority -> Admission -> Execution -> Evidence`

The agent and sandbox are never the authority. Neither may issue credentials, grant quota, admit themselves, modify authoritative usage, or write the final qualification verdict.