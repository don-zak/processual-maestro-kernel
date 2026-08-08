# Settings Space — Runtime, Readiness, and Retirement Review

Status date: 2026-08-08
Branch: `feat/a3-admin-marketplace-original-offers`
Scope: the client/admin Settings space, its runtime dependencies, UI assets, API surface, operational qualifications, and staged retirement candidates.

## Review rule

Nothing is deleted merely because its name looks old. A file or endpoint may be removed only after all of the following are true:

1. no current runtime composition root imports or loads it;
2. no current UI calls it;
3. no active service imports its symbols;
4. an explicit regression test protects the replacement path;
5. compatibility impact is understood;
6. removal is performed as a small isolated change and CI is reviewed before the next removal.

## Active composition root

The Settings runtime is currently composed through:

- `processual_api/main.py` -> includes `processual_api.routers.settings.router`;
- `processual_api/settings.py` -> process/environment configuration and production fail-closed checks;
- `processual_api/routers/settings.py` -> Settings HTTP API and client/admin operational actions;
- `processual_api/schemas/settings.py` -> Settings request/response models;
- `processual_api/static/index.html` -> Settings console surface and `js/pages/settings.js` load;
- `processual_api/static/js/pages/settings.js` -> primary current client Settings behavior;
- `processual_api/static/js/app.js` -> Settings navigation plus dynamic loading of the Stage-18 Settings layout/operations assets;
- `processual_api/static/js/settings_layout_18.js` and `processual_api/static/css/settings_layout_18.css` -> active Settings layout behavior/style;
- `processual_api/static/js/settings_operations_18.js` and `processual_api/static/css/settings_operations_18.css` -> active Settings operational behavior/style.

These files are **ACTIVE / DO NOT DELETE** until composition is intentionally replaced.

## Active runtime dependencies

`processual_api/routers/settings.py` currently depends on active platform capabilities including:

- authentication and scope enforcement;
- encrypted provider-secret storage;
- integration operational profiles and readiness;
- provider metadata;
- billing/plan policy and subscription analytics;
- verified client plan application;
- client usage summary and usage ledger;
- supervision RBAC;
- supervisor session-key issuance/revocation;
- admin audit events.

Commercial Settings top-up contract modules are not dead files. In particular, `commercial_top_up_application_service.py` imports `TopUpCheckoutChannel` from `commercial_settings_top_up_checkout_contracts.py`, so the checkout contract remains an active dependency even if its original status strings still say `draft_review`.

## Current client UI contract

The current `pages/settings.js` uses the provider-connection API:

- `GET /settings/provider-connection`
- `PUT /settings/provider-connection/setup`
- `DELETE /settings/provider-connection/setup`
- `POST /settings/provider-connection/test`

It also uses the client-scoped usage summary:

- `GET /settings/client/usage-summary`

The current UI does **not** call the legacy `/settings/llm-provider*` paths and does **not** call `/settings/usage-summary`.

## Retirement candidates

These are candidates for staged retirement, not immediate deletion.

| Candidate | Current classification | Reason | Required next step before removal |
|---|---|---|---|
| `PUT /settings/llm-provider` | LEGACY COMPATIBILITY | superseded in current UI by `/provider-connection/setup` | add/retain replacement-path tests, inventory external consumers, then deprecate |
| `DELETE /settings/llm-provider` | LEGACY COMPATIBILITY | current UI uses `/provider-connection/setup` delete | same as above |
| `POST /settings/llm-provider/test` | LEGACY COMPATIBILITY | current UI uses `/provider-connection/test`; provider-connection currently delegates to legacy test function internally | first extract shared provider-test service/helper, then deprecate endpoint |
| `GET /settings/usage-summary` | LEGACY/ADMIN-AMBIGUOUS | current client UI uses `/settings/client/usage-summary` | identify external/API consumers and intended admin semantics before deprecation |
| notification persistence/test endpoints | REVIEW REQUIRED | no current calls from `pages/settings.js` | verify other clients/docs/automation before marking deprecated |
| legacy Settings fields in file-backed JSON | REVIEW REQUIRED | old persisted data may exist even after UI changes | add migration/compatibility read test before removing keys |

## Do-not-delete findings

The following looked old by naming/version but are currently active and must not be removed:

- `settings_layout_18.js` / `settings_layout_18.css`: dynamically loaded by `app.js` and initialized when Settings is opened;
- `settings_operations_18.js` / `settings_operations_18.css`: dynamically loaded by `app.js` and initialized when Settings is opened;
- `commercial_settings_top_up_checkout_contracts.py`: imported by the active top-up application service;
- `commercial_settings_top_up_ui_contracts.py`: imported by the checkout contract;
- `schemas/settings.py`: imported by the Settings router;
- `routers/settings.py`: included by `main.py`.

## Operational qualification matrix

| Area | Current state | Qualification needed |
|---|---|---|
| Main router wiring | ACTIVE | regression test that main includes Settings router |
| Settings SPA wiring | ACTIVE | regression test for index -> pages/settings.js and app -> Stage-18 assets |
| Provider connection | ACTIVE | API security, encrypted-secret, setup/clear/test regression |
| Client usage summary | ACTIVE | authenticated-client isolation and UI contract tests |
| Subscription status | ACTIVE | billing-backed state and fail-closed subscription tests |
| API-key administration | ACTIVE | admin scope/RBAC, create/update/revoke regression |
| Client requests | ACTIVE | client isolation, admin review, status and supervisor-response regression |
| Integration readiness | ACTIVE | client/admin readiness regression |
| Supervisor session keys | ACTIVE | issuance/list/revocation and scope regression |
| General preferences | ACTIVE | persistence/default merge regression |
| Notifications | REVIEW REQUIRED | determine supported product use before keeping or retiring |
| Legacy LLM-provider endpoints | DEPRECATION CANDIDATE | external-consumer audit + compatibility window |
| Legacy usage-summary endpoint | DEPRECATION CANDIDATE | external-consumer audit + semantic replacement decision |
| File-backed Settings persistence | TECHNICAL DEBT / ACTIVE | corruption, atomic replace, backup, multi-process/storage-topology qualification |

## Persistence risk

Settings are currently stored in per-user JSON files under `processual_api/data` using a file lock, temporary file, backup, and atomic replacement. This is functional for the current topology but should not be assumed to provide cross-node shared persistence. Before horizontally scaling the Settings write path, production qualification must explicitly decide whether Settings remain node-local or move to a shared authoritative store.

No storage rewrite is authorized by this review alone.

## Staged cleanup plan

### Stage 0 — inventory and guardrails

- Keep all current runtime files.
- Add a wiring regression test protecting the active Settings composition and replacement endpoints.
- Record retirement candidates without changing external behavior.

### Stage 1 — remove internal duplication safely

- Extract provider connection testing into one private/shared helper so `/provider-connection/test` no longer depends on the legacy endpoint function.
- Add tests proving encrypted secrets are never returned and provider test behavior is unchanged.
- Keep legacy HTTP routes temporarily as compatibility wrappers.

### Stage 2 — explicit endpoint deprecation

- Mark legacy `/llm-provider*` and, if confirmed, `/usage-summary` as deprecated compatibility routes.
- Ensure the current UI contains no calls to them.
- Run API/contract CI and inventory external consumers.

### Stage 3 — first removals

- Remove only legacy routes that have zero supported consumers after the compatibility window.
- Remove their route-specific tests and replace them with negative route-absence tests only when removal is intentional.
- Do not delete shared crypto/provider helpers that remain used by current paths.

### Stage 4 — file cleanup

- Re-run repository reference inventory.
- Delete files only when no runtime import, static load, test contract, migration, or supported compatibility requirement remains.
- One file or tightly coupled pair per change, followed by targeted tests and CI review.

## Current decision

The Settings space is active and operationally broad. The first review found **no Settings-named runtime file that is safe to delete immediately**. Several endpoints are credible retirement candidates, but deleting them now would mix compatibility cleanup with runtime refactoring.

The safe next implementation step is Stage 1: decouple the current provider-connection test path from the legacy `/llm-provider/test` endpoint function, protect the replacement contract with tests, and only then begin endpoint retirement.
