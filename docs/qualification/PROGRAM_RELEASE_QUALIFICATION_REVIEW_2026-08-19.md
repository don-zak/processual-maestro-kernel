# Program Release Qualification Review — 2026-08-19

**Status:** NON-REAL-ENVIRONMENT REVIEW IN PROGRESS — NOT PRODUCTION AUTHORITY

## Scope

This review expands qualification beyond packaging and the public/private trust boundary into the release-critical product surfaces:

- repository/workflow inventory;
- identity registration and selected-plan intent;
- public plan catalog and plan eligibility;
- plan -> entitlement -> quota projection;
- subscription activation and runtime bootstrap;
- quota consumption, idempotency, grace limits, and balance enforcement;
- admin/supervisor operational workspace;
- production environment template and secret-delivery contract;
- packaging, Docker, source-boundary, and sandbox qualification;
- real-staging prerequisites and release-candidate transition rules.

This record does not convert synthetic or CI evidence into provider, staging, operator-network, or production proof.

## Repository-wide inventory observations

The exact qualification branch contains multiple CI surfaces rather than one monolithic release workflow, including public CI, packaging qualification, public Docker, sandbox integration qualification, settings-space qualification, release gates, security, load/benchmark/soak workflows, staging-canary controls, CAMARA source contracts, and the new Program Release Qualification gate.

The release decision therefore MUST be based on a gate matrix and exact evidence-bearing SHA, not on one green check name.

## Registration and plan eligibility

Registration is plan-led but fail-closed:

- direct registration resolves the selected plan through the authoritative public plan journey;
- the selected plan must match the registration account mode;
- assessment-required plans are rejected from direct registration;
- monthly/annual billing period is required only for a selected direct plan;
- registration persists the selected plan intent and billing period without activating commercial runtime authority.

Qualification expectation: no registration response or UI route may imply active entitlement/quota until the commercial activation gate has completed.

## Plan, entitlement, and quota authority

The authoritative commercial projection cross-checks the commercial catalog against the plan fulfillment catalog. A projection contains:

- plan code;
- versioned entitlement profile reference;
- versioned quota profile reference;
- monthly Maestro Unit allowance;
- entitlement codes.

The projection refuses catalog/fulfillment divergence. The quota profile is derived from the same projection, so quota limits are not an unrelated UI constant.

Current fulfillment rules are quota-based and explicitly reject seat-based consumption. The canonical commercial metric is `maestro_units`; historical `credits` is compatibility-only.

## Subscription activation and runtime authority

Direct activation is gated by authoritative order, contract, payment evidence where required, customer/channel eligibility, offer validity, plan existence, and entitlement/quota profile bindings.

Successful activation creates the active subscription and entitlement activation and bootstraps runtime plus quota accounts inside the surrounding transaction. Replays must match the original binding.

This is a key launch invariant: an active subscription must not exist as a commercial shell disconnected from runtime entitlement/quota authority.

## Quota consumption and protection

Quota usage requires all of the following:

- positive bounded usage input;
- idempotency contract;
- active subscription;
- matching customer identity;
- authoritative runtime record;
- runtime access stage that allows usage;
- matching quota cycle, metric, subscription, customer, and time window;
- available units >= requested units;
- additional authoritative delinquency/grace state and degraded-grace cap when runtime is in grace.

Runtime operational capacity and external execution fan-out remain separate operational controls from commercial quota. They must not be marketed or audited as a substitute for plan quota.

## Public plan representation

Direct-registration plans may expose included quota only when the quota can be projected from the authoritative fulfillment catalog. Assessment plans must display assessment-controlled quota/price semantics instead of fabricated public limits.

The release qualification test locks these properties and prevents plan-page drift from commercial/runtime authority.

## Supervisor/admin readiness

The admin shell contains operational navigation for Admin Market, API keys, clients, usage, program progress, system health, settings, and operator/pilot handoff. The supervisor home/readiness surfaces explicitly state that backend enforcement remains authoritative and are intended as visibility surfaces.

Release criteria for the admin area:

1. protected backend scopes remain the authorization source;
2. UI visibility never grants operational authority;
3. no raw API keys/provider secrets/private mathematical internals are rendered;
4. usage and subscription analytics distinguish unavailable/not-wired data from zero/healthy data;
5. release/runtime/provider/staging readiness labels must not overstate authority;
6. admin regressions run in the Program Release Qualification gate.

## Environment and Infisical qualification

`.env.production.example` remains a names/placeholders reference, not a secret store. The new `config/infisical/production-secret-manifest.json` classifies secret keys, non-secret configuration keys, real-staging evidence keys, fail-closed feature flags, and prohibited long-lived Infisical credentials.

The intended Infisical model is:

- GitHub OIDC -> Infisical Machine Identity for short-lived CI access;
- runtime-only secret injection;
- no secret values in Git;
- no long-lived `INFISICAL_TOKEN`/Universal Auth client secret/service token in the repository;
- feature flags for unqualified top-up paths remain false.

The attached external Cloud Run reference report recommends Google Secret Manager. That recommendation is not silently replaced. Before real staging, the deployment architecture must explicitly choose one secret authority or document a controlled bridge between Infisical and Google Secret Manager, including ownership, rotation, audit, and failure semantics. Duplicate unmanaged secret authority is not acceptable.

## Additions derived from the Cloud Run reference report

The report adds useful operational acceptance criteria that CI alone cannot provide:

- immutable image digest promotion rather than `latest`;
- Cloud SQL PostgreSQL as commercial/runtime source of truth;
- Redis as rebuildable coordination/cache, not commercial truth;
- migration as a controlled job, not application startup behavior;
- pre-migration backup plus restore rehearsal to a separate staging database;
- idempotent backfill replay;
- real health/readiness smoke after migration;
- complete commercial E2E;
- load/concurrency/security/observability qualification;
- same-digest progression from staging to release candidate/pilot;
- explicit rollback and evidence references.

These criteria are adopted as future real-environment gates, not marked complete by this review.

## New CI evidence surface

`.github/workflows/program-release-qualification.yml` now groups release-critical non-real-environment checks into one explicit program gate:

- registration and plan qualification;
- subscription entitlement/quota qualification;
- supervisor workspace regression;
- production environment/Infisical contract qualification;
- Ruff/Flake8;
- secret scan;
- dependency audit.

The gate complements, rather than replaces, Packaging Qualification, Public Docker Build, CAMARA Public Source Contracts, Sandbox Integration Qualification, and existing domain workflows.

## Remaining blockers before release authority

### Repository/general packaging

- select and prove a real opaque reference issuance/registry/private-resolution topology;
- migrate remaining raw-score/vector legacy browser/router/report surfaces after that topology exists;
- complete dependency/license review and private-error-surface review;
- produce public container-image SBOM;
- establish immutable release-candidate image digest evidence;
- qualify private image/SBOM inside the private trust domain;
- reconcile deployment/configuration/operator/admin/customer/migration/incident documentation;
- final obsolete terminology/file cleanup;
- run exact release-candidate gate matrix on one immutable artifact.

### Real staging

- actual environment exists and is reachable;
- final secret authority/injection path is selected and proven;
- Cloud SQL/Redis/network/runtime/IAM are configured with least privilege;
- real backup reference exists;
- migration job and backfill replay succeed;
- restore rehearsal succeeds against a separate restored instance;
- commercial E2E proves checkout/provider webhook/order/subscription/runtime/quota/usage plus renewal/failure/grace/suspension/cancellation/refund;
- browser/domain/TLS/load/concurrency/observability/rollback evidence exists;
- provider/operator-specific proofs remain independent.

## Authority state after this review

- `RepositoryReconciliationComplete=false`
- `GeneralPackagingComplete=false`
- `PrivateRuntimeAuthorityGranted=false`
- `runtime_connector_approved=false`
- `provider_sandbox_proven=false`
- `operator_network_qos_proven=false`
- `RealStagingQualified=false`
- `ProductionAuthorityGranted=false`

## Continuation rule

`docs/qualification/PROGRAM_QUALIFICATION_CONTINUATION_CAPSULE.md` is mandatory carry-forward context for every later workspace/branch/PR/release-stage handoff. Any future status update must preserve unresolved blockers and exact evidence-bearing SHAs/runs until independently superseded.
