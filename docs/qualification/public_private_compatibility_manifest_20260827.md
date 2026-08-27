# Public / Private Compatibility Manifest — 2026-08-27

## Purpose

This manifest defines the current authority boundary between the public and private Processual Maestro Kernel repositories before launch. It is a compatibility and evidence document, not a production launch approval.

## Pinned references

- Public repository: `don-zak/processual-maestro-kernel`
- Public `main`: `d2a0baa912efc384c57d086a4d67a8ac29d20987`
- Public qualification head used for the final release gate before this document: `21f5db6217418df77165dd83faf2217cff58d9af`
- Public Program Release Qualification #748: SUCCESS on `21f5db6217418df77165dd83faf2217cff58d9af`
- Public Launch Closeout Gate #715: SUCCESS on `21f5db6217418df77165dd83faf2217cff58d9af`
- Private repository: `don-zak/processual-maestro-kernel-private`
- Private `main`: `84e3354cd43802176ee93ed94f72144341c0068b`
- Private security-readiness branch: `agent/prelaunch-security-readiness-20260827`
- Private security patch head: `a80923fa482f4412c4ce3980f1d262a35bdb42ec`
- Private draft PR: #55

## Authority boundary

### Public runtime authority

The public repository is the current source of truth for the externally reviewable application runtime and commercial qualification surface, including:

- registration and identity delivery flows;
- MFA and authentication key-ring configuration;
- public browser entry surfaces and security headers;
- Admin Marketplace and supervisor workspace;
- commercial plans, subscriptions, entitlements and quota consumption;
- billing and Lemon Squeezy integration contracts;
- Tunisia-local payment/top-up feature gates;
- production environment contract and Infisical qualification;
- PostgreSQL / Redis authority gates used by release qualification;
- public deployment and limited-pilot documentation.

### Private engine authority

The private repository remains the source of truth for proprietary CGT/private-engine material and its private validation surfaces, including:

- proprietary `cgtlib.private` implementation;
- private bridge/security workflows;
- private monorepo packaging and private CGT validation;
- higher private coverage threshold and private deployment-readiness gates.

## Shared compatibility surfaces

The following must be treated as explicit compatibility contracts rather than assumed identical files:

1. Package and Python version contract (`pyproject.toml`, Python 3.14, package versioning).
2. Public-to-private CGT API / import contract.
3. Runtime settings and environment-variable compatibility.
4. Serialization/storage formats crossing public/private boundaries.
5. Docker/build target compatibility.
6. API schemas consumed by external clients.
7. Security and dependency baselines.
8. Release/version identifiers.

## Verified drift that must remain explicit

The repositories are intentionally not byte-identical and currently contain material configuration drift.

### Administrator/authentication model

Public runtime uses modern commercial/authentication configuration including `MAESTRO_ADMIN_EMAIL`, `MAESTRO_ADMIN_PASSWORD`, delivery peppers/key rings, MFA key rings and Admin Marketplace payment-destination encryption keys.

Private `main` still exposes the older `ADMIN_USERNAME` / `ADMIN_PASSWORD_HASH` administrator configuration model.

This difference means the private repository must not be treated as the authoritative production application-settings template without a deliberate synchronization change.

### Dependency/build contract

Both repositories identify as version `2.0.0`, but their dependency declarations and packaging details are not identical. Public qualification currently carries the newer commercial/runtime dependency surface. Private CI retains its own constrained dependency lock and private packaging workflow.

Semantic version equality therefore does **not** imply configuration or dependency parity.

### Coverage policy

- Public repository configured coverage floor: 70%.
- Private repository configured coverage floor: 85%.

These are policy differences, not proof that the two trees provide the same behavioral coverage.

## Private supply-chain security status

A scheduled private Security Scan on 2026-08-24 identified `pip 26.1.2` as affected by `PYSEC-2026-3721`; the published fixed version was `26.2`.

PR #55 changes only the CI constraint from `pip==26.1.2` to `pip==26.2`.

Two executions of the private PR CI job failed before runner allocation: both reported no steps, no runner name and `runner_id=0`. Therefore these runs are classified as **GitHub Actions runner-provisioning failures**, not code/test failures. The dependency fix remains pending executable CI proof before merge.

## Public release proof

On public qualification head `21f5db6217418df77165dd83faf2217cff58d9af`, Program Release Qualification #748 completed successfully across:

- registration and plan qualification;
- subscription entitlement and quota qualification;
- supervisor workspace qualification;
- public UI, browser security and legacy quarantine qualification;
- compatibility retirement qualification;
- production environment and Infisical contract qualification;
- static quality gate;
- secret scan;
- dependency audit.

Launch Closeout Gate #715 also completed successfully, including the real PostgreSQL/Redis authority gate and guarded legacy quota retirement proof.

## Versioning recommendation before production launch

Before a production release, maintain two explicit identifiers:

- **Public Runtime Version** — application/commercial/API release.
- **Private Engine ABI/Compatibility Version** — proprietary CGT/private-engine contract.

A release is compatible only when the runtime version is mapped to a tested private-engine compatibility version in this manifest or its successor.

## Pre-launch decision

- Public runtime qualification: **GREEN at pinned head**.
- Splash archive/quarantine closeout: **GREEN at pinned head**.
- Private supply-chain patch: **PATCHED ON BRANCH, CI PROOF BLOCKED BY RUNNER PROVISIONING**.
- Public/private compatibility: **EXPLICITLY DOCUMENTED; NOT BYTE-PARITY**.
- Production launch: **NOT AUTHORIZED BY THIS DOCUMENT**.
