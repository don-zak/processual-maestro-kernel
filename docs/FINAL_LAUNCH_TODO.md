# Final Launch TODO

This file is the authoritative pre-launch checklist for Processual Maestro. A task is not complete because code exists; it is complete only when its acceptance evidence is recorded and the relevant CI/runtime qualification is green.

## P0 — Account Recovery Hardening

- [ ] Require a second independent recovery factor before password reset completion.
  - Preferred launch contract: verified recovery email link/token **plus** one additional factor that was enrolled before the recovery attempt.
  - Supported second factors should be ordered by strength: passkey/security key or recovery code first; verified phone OTP may be supported as an additional fallback.
  - SMS/phone OTP must never become the sole recovery authority because of SIM-swap/number-reassignment risk.
  - The existing password must **not** be mandatory in the Lost Access flow; if the user still knows the current password, use the normal password-change/step-up flow instead of account recovery.
  - For Platform Admin accounts, require the stronger available second factor and fail closed if no qualified factor exists.
- [ ] Add verified phone-number enrollment and change controls.
  - Phone number must be verified before it can be used for recovery.
  - Changing/removing a recovery phone requires an authenticated step-up and must invalidate or cool down recovery use of the new number according to policy.
  - Never expose whether a phone/email/account exists through recovery responses.
- [ ] Add short-lived single-use OTP confirmation for phone recovery.
  - Bind OTP to recovery request + account + intended action.
  - Enforce expiry, attempt limits, resend cooldown, replay protection, and rate limiting.
  - Store only a one-way verifier; never log raw OTP values.
- [ ] Add recovery factor downgrade protection.
  - An attacker controlling one factor must not be able to replace the second factor and immediately use it to recover the account.
  - Introduce a cooling-off / notification policy for sensitive recovery-factor changes.
- [ ] Keep the existing post-recovery revocation contract.
  - Revoke refresh tokens, active sessions, action tokens, external supervisor/API keys, and existing MFA factors as required by policy.
  - Require MFA reenrollment before restoring privileged authority.
  - Do not auto-login or auto-restore Platform Admin authority after recovery.
- [ ] Add full tests for recovery abuse cases.
  - Wrong/expired/replayed OTP.
  - Rate-limit exhaustion.
  - Factor replacement race.
  - SIM/phone fallback cannot bypass stronger configured factor policy.
  - No secret/token/OTP/recipient leakage in logs or evidence.
  - Concurrent recovery requests cannot create multiple valid completion authorities.

## P1 — Recovery Delivery Runtime / Resend

- [ ] Qualify the embedded delivery worker on the exact release SHA.
  - `AUTH_DELIVERY_EMBEDDED_WORKER_ENABLED=true`.
  - Poll interval explicitly configured.
  - Hosted logs show `identity_delivery_embedded_worker_started`.
  - Hosted logs show safe `identity_delivery_embedded_worker_batch_completed` evidence.
  - No secret-bearing exception text in logs.
- [ ] Perform exactly controlled Lost Access E2E qualification.
  - Recovery start returns 202 without account enumeration.
  - Outbox item is claimed once.
  - Resend accepts the delivery.
  - Delivery reaches the intended physical inbox.
  - Recovery link/token never appears in server request logs.
  - Password reset completes.
  - Old sessions/tokens/API keys are revoked.
  - MFA reenrollment completes.
  - Fresh login restores valid authority only after required authentication factors.
- [ ] Qualify dead-letter/retry behavior and stale recovery-message finalization.

## P2 — External Evaluation Qualification

- [ ] Platform Admin authority endpoint returns authorized state only for a valid active Platform Admin session.
- [ ] Create External Evaluation grant.
- [ ] Issue Evaluation API key; raw key is shown once only and is never persisted/redisplayed/logged.
- [ ] Confirm key delivery and customer receipt acknowledgment.
- [ ] Customer runtime status displays credential state, evaluation type, quota limit, admitted usage, remaining quota, latest execution, persisted evidence, and `production_execution=false`.
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
- [ ] Account Recovery E2E green with second-factor hardening.
- [ ] External Evaluation E2E green.
- [ ] Required billing/provider smoke tests green or explicitly waived as non-launch scope.
- [ ] Private overlay/supply-chain qualification green if private production components are part of launch.
- [ ] No unresolved launch-blocking P0/P1 issues.
- [ ] Final audit/report reviewed by a human operator; system does not auto-declare production readiness.
- [ ] Merge/release only after explicit operator authorization.

## Non-Negotiable Authority Invariant

`Policy / Authority -> Admission -> Execution -> Evidence`

The agent and sandbox are never the authority. Neither may issue credentials, grant quota, admit themselves, modify authoritative usage, or write the final qualification verdict.
