# Program Qualification Continuation Capsule

**Purpose:** canonical carry-forward record for every future branch, workspace, review session, release-candidate handoff, staging handoff, and production-readiness review.

**Rule:** this file is not a declaration of production readiness. It records the minimum context that MUST be carried forward before qualification work continues elsewhere.

## Current authority state

- `RepositoryReconciliationComplete=false`
- `GeneralPackagingComplete=false`
- `PrivateRuntimeAuthorityGranted=false`
- `runtime_connector_approved=false`
- `provider_sandbox_proven=false`
- `operator_network_qos_proven=false`
- `RealStagingQualified=false`
- `ProductionAuthorityGranted=false`

No later workspace may infer a `true` value from green CI alone. Each authority must be changed only by its own evidence-bearing gate.

## Architectural invariants

1. Public repository owns governance, orchestration, authentication/commercial contracts, entitlement/quota enforcement, public-safe adapters, release controls, and sanitized private-evaluation contracts.
2. Private repository owns proprietary equations, weights, thresholds, calibration, vectors, raw scores, and private mathematical intermediates.
3. Public-to-private evaluation uses bounded opaque references only.
4. Private-to-public evaluation returns exactly: `existence_rank`, `dominant_constraint`, `next_gate`, `confidence_band`, `explanation_code`, `policy_version`.
5. Public code must never discover or package private mathematical modules.
6. Protected evaluation fails closed when a private runtime/provider/resolver is unavailable.
7. A reference must never be fabricated from answer text, scores, vectors, or private values.

## Commercial and quota invariants

1. Registration may select only an authoritative direct-registration plan compatible with account mode.
2. Assessment-required plans must not become direct self-service subscriptions.
3. Subscription activation requires authoritative entitlement and quota profile bindings.
4. Activation bootstraps runtime access and quota accounts atomically with the subscription transaction.
5. Maestro usage is quota-based, not seat-based.
6. Usage requires an active subscription, matching customer/runtime/cycle, allowed runtime stage, available units, and idempotent ledger semantics.
7. Grace usage is separately bounded by authoritative delinquency state and a degraded-grace cap.
8. A public plan must never advertise a quota that is not bound to the authoritative fulfillment catalog.
9. Commercial quota, runtime capacity guards, and external execution fan-out are distinct controls and must not be represented as interchangeable.

## Supervisor/admin invariants

- Backend scopes and policy enforcement remain authoritative.
- Admin UI is an operational/readiness surface; visibility must not become authorization.
- No raw API keys, provider secrets, private mathematical internals, or secret values may be rendered into the admin surface.
- Admin Marketplace, usage, program progress, system health, and system settings must remain covered by regression gates before release.

## Secret-delivery / Infisical invariants

- Repository contains names/contracts only, never real secret values.
- Preferred GitHub CI authentication is short-lived GitHub OIDC to an Infisical Machine Identity.
- Long-lived `INFISICAL_TOKEN`, Universal Auth client secret, or service token must not be committed.
- Runtime secret injection is separate from configuration defaults.
- Fail-closed commercial feature flags remain false until their real-environment evidence gates are complete.
- `config/infisical/production-secret-manifest.json` is the canonical value-free secret/config inventory for production qualification.

## Current blocking sequence

1. Finish repository-wide non-real-environment release qualification and address any CI regression.
2. Select and review a real opaque-reference issuance/registry/private-resolution topology; do not invent one from hashes or public raw data.
3. Migrate remaining legacy raw-score/vector browser/router/report surfaces only after real reference issuance/resolution exists.
4. Complete General Packaging: dependency/license review, private-error-surface review, public container SBOM, immutable release-candidate image digest, private image qualification/SBOM, configuration/document reconciliation.
5. Provision real staging with separately controlled secrets, database/cache/network/runtime resources.
6. Execute migration backup, migration/backfill/idempotency replay, restore rehearsal, and record real evidence references.
7. Execute complete commercial E2E including checkout/provider webhook/order/subscription/runtime/quota/usage and renewal/failure/grace/suspension/cancellation/refund paths.
8. Execute real staging browser, security, load/concurrency, observability, rollback, provider, and operator proofs.
9. Promote one immutable digest to release candidate, then controlled pilot, then GA only after acceptance criteria pass.

## Transition protocol

Whenever qualification moves to a new branch, PR, workspace, agent, or review session:

1. Read this capsule first.
2. Re-fetch the exact current public and private PR heads and CI results.
3. Preserve all authority flags unless new evidence explicitly changes one.
4. Carry forward every unresolved blocker and exact evidence-bearing SHA/run identifier.
5. Update this capsule when a gate changes; never rely on conversational memory alone.
6. Keep public/private trust-boundary constraints unchanged unless an explicit architecture decision supersedes them.

## Current PR safety

- Public qualification PR remains Draft/Open until an explicit review decision.
- Private trust-boundary PR remains Draft/Open until an explicit review decision.
- No merge, rebase, force-push, auto-merge, staging mutation, or production mutation is authorized by this capsule.
