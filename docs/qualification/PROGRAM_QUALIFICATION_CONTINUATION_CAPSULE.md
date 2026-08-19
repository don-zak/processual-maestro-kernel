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
10. A direct-plan browser journey must preserve both `plan_id` and a validated `billing_period` from the offer page through registration. If a plan registration link is incomplete or carries an unsupported billing period, the browser must fail closed before submission and the backend remains authoritative.

## Public UI / browser truth invariants

- Public UI and package metadata must not claim production readiness while `ProductionAuthorityGranted=false`.
- Delivered splash and console HTML are rewritten at the response boundary to qualification wording until production authority is independently granted.
- Public browser responses carry `X-Content-Type-Options`, `X-Frame-Options`, HSTS, `Referrer-Policy`, `Permissions-Policy`, and a Content Security Policy.
- CSP currently restricts external browser dependencies to the explicitly required Google Fonts and jsDelivr sources, blocks objects and framing, constrains forms/base/connect, and upgrades insecure requests.
- Current console/splash implementation still contains inline script/style behavior, therefore CSP temporarily requires `'unsafe-inline'` for script/style compatibility. Removing that exception requires a controlled extraction/nonce/hash migration and rendered-browser proof; do not delete it by assertion alone.
- `X-XSS-Protection` is explicitly disabled (`0`); CSP is the browser content policy control.
- Static source text, browser-delivered text, package metadata, and backend authority are separate review surfaces; rendered HTTP behavior is the release-relevant truth.
- Browser automation, accessibility scan, viewport/support matrix, error/degraded-state journeys, and external asset pinning/self-hosting remain open qualification work.

## Legacy component quarantine invariants

- `docs/qualification/LEGACY_COMPONENT_QUARANTINE_REGISTER_R1.md` is the canonical parts-control register for superseded, compatibility-only, quarantined, active-legacy, and deletion-candidate components.
- `processual_api/static/js/adapters/governor.js`, `processual_api/static/js/adapters/cgt.js`, `processual_api/static/js/pages/governor.js`, and `processual_api/static/js/pages/cgt.js` are `QUARANTINED_SOURCE`: retained in Git for review, removed from delivered console HTML, hidden from console navigation/page delivery, and direct HTTP requests return `410 Gone`.
- Quarantined source must not be reconnected merely to restore historical behavior. Replacement requires the sanitized opaque-reference evaluation path after real issuance/resolution exists.
- `processual_api/billing/subscription_catalog.py` is `COMPATIBILITY_ONLY`; new production imports are forbidden by qualification tests and canonical code must use `processual_api.billing.pricing_catalog`.
- `processual_api/routers/client_provider_alias_18.py` is `COMPATIBILITY_ONLY`; the current Settings UI uses `/settings/provider-connection`, while the deprecated alias remains only for controlled external compatibility. New internal application/UI dependencies on `/client/provider-connection` are forbidden by qualification tests.
- `processual_api/routers/cgt_governor.py` remains `ACTIVE_LEGACY_DEBT`, not dead code and not a deletion candidate. It must not be partially amputated before opaque-reference issuance/resolution and dependent browser/router/report migrations are complete.
- Deletion requires a dedicated evidence-bearing review proving no runtime, import, route, dynamic loader, migration, operator, test, documentation, external-compatibility, or rollback dependency remains.

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

## General Packaging controls already implemented

The following are non-real-environment controls and must be re-proven on the exact current head before being cited as evidence:

- Python dependency vulnerability audit with `pip-audit`;
- Python CycloneDX dependency SBOM;
- installed-environment dependency/license metadata inventory in `release-evidence/dependency-license-review.json`;
- public/private error-surface regression proving generic private-evaluation errors and no exception-detail forwarding;
- public wheel/sdist build, metadata validation, installed-wheel smoke, reference-data packaging checks, and private-source exclusion;
- public Docker build and fail-closed trust-boundary smoke;
- public container CycloneDX and SPDX SBOM generation from the built image;
- public container SBOM scan preventing private-module path leakage;
- ephemeral PR image identity evidence without publishing an image or inventing a release digest;
- public offer-to-registration plan/billing-period linkage regression;
- delivered public UI authority-truth, package-metadata truth, CSP, and baseline browser-security regression;
- rendered HTTP legacy-console quarantine regression and source-reconnection guards for compatibility-only components.

The dependency-license inventory is evidence of package metadata only. It is not a legal license-compatibility opinion.

## General Packaging blockers still open

- The repository/package owner must explicitly choose and declare the product's distribution license before external distribution; no license is selected by automated qualification.
- An immutable release-candidate image digest is still required from a real published release-candidate artifact. A PR-only image ID is not a substitute.
- Private image qualification and private image SBOM remain private-trust-domain work.
- Final configuration/deployment/operator/admin/customer/migration/incident documentation reconciliation and obsolete terminology cleanup remain open.
- General Packaging cannot close while opaque-reference implementation/proof and legacy public/private boundary migration remain unresolved.
- Browser qualification remains incomplete until automated rendered-page journeys, accessibility, viewport/support policy, network/error-state behavior, and CSP inline/external-asset hardening are reviewed and evidenced.
- Compatibility-only and quarantined components remain in-tree until their explicit deletion gates pass; quarantine is not equivalent to deletion authority.

## Opaque-reference topology status

- The public contract accepts only bounded `formation_ref`, `evidence_ref`, `context_ref`, and `evaluated_at`.
- The private repository defines a `PrivateReferenceResolver` protocol and generic failure behavior.
- `docs/architecture/OPAQUE_REFERENCE_TOPOLOGY_DECISION_R1.md` now records a **proposed, review-required, non-authoritative** topology: durable PostgreSQL shared-safe reference metadata, a dedicated public issuer, and controlled private resolution through a broker/service boundary.
- Redis is explicitly not selected as the sole durable reference authority; browser-generated/hash-derived references remain prohibited.
- The proposal does not select the exact private storage technology, network transport, secret authority, credentials, or production rollout.
- No concrete registry migration, issuer implementation, private resolver backing mapping, or runtime connector is authorized yet.
- No future workspace may manufacture references by hashing answer text, scores, vectors, or private data merely to satisfy the API shape.

## Current blocking sequence

1. Re-prove all current public CI gates on the exact current public head after any modification.
2. Continue legacy-component inventory and quarantine: classify proven compatibility/obsolete surfaces, prevent new dependencies, and advance components to deletion candidates only after explicit dependency review.
3. Continue public browser remediation: rendered journey tests, accessibility, supported viewport contract, error/degraded-state UX, CSP inline reduction, and external-asset pinning/self-hosting review.
4. Review/approve or revise `OPAQUE_REFERENCE_TOPOLOGY_DECISION_R1.md`; only then define the shared-safe schema and public issuer interface.
5. Implement private resolver/broker only in the private repository after private backing mapping is independently approved.
6. Migrate remaining legacy raw-score/vector browser/router/report surfaces only after real reference issuance/resolution exists.
7. Complete remaining General Packaging blockers: product license decision, immutable release-candidate image digest, private image qualification/SBOM, and final documentation reconciliation.
8. Provision real staging with separately controlled secrets, database/cache/network/runtime resources.
9. Execute migration backup, migration/backfill/idempotency replay, restore rehearsal, and record real evidence references.
10. Execute complete commercial E2E including checkout/provider webhook/order/subscription/runtime/quota/usage and renewal/failure/grace/suspension/cancellation/refund paths.
11. Execute real staging browser, security, load/concurrency, observability, rollback, provider, and operator proofs.
12. Promote one immutable digest to release candidate, then controlled pilot, then GA only after acceptance criteria pass.

## Transition protocol

Whenever qualification moves to a new branch, PR, workspace, agent, or review session:

1. Read this capsule first.
2. Re-fetch the exact current public and private PR heads and CI results.
3. Preserve all authority flags unless new evidence explicitly changes one.
4. Carry forward every unresolved blocker and exact evidence-bearing SHA/run identifier.
5. Update this capsule when a gate changes; never rely on conversational memory alone.
6. Keep public/private trust-boundary constraints unchanged unless an explicit architecture decision supersedes them.
7. Read the legacy-component quarantine register before reconnecting, deleting, or replacing any compatibility/quarantined component.

## Current PR safety

- Public qualification PR remains Draft/Open until an explicit review decision.
- Private trust-boundary PR remains Draft/Open until an explicit review decision.
- No merge, rebase, force-push, auto-merge, staging mutation, or production mutation is authorized by this capsule.
