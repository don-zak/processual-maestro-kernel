# Settings Space — Runtime, Readiness, and Retirement Review

Status date: 2026-08-08
Branch: `feat/a3-admin-marketplace-original-offers`
Scope: the client/admin Settings space, its runtime dependencies, UI assets, API surface, operational qualifications, output quality, load behavior, and staged retirement candidates.

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
- `processual_api/routers/settings_subscription_runtime.py` -> replaces the legacy subscription route with the authoritative subscription-access runtime and retires legacy subscription helpers at composition time;
- `processual_api/routers/client_api_keys_18.py` -> client self-service sandbox key operations attached to the Settings router;
- `processual_api/routers/client_provider_alias_18.py` -> deprecated provider-status compatibility alias attached to the Settings router;
- `processual_api/schemas/settings.py` -> Settings request/response models;
- `processual_api/static/index.html` -> Settings console surface and `js/pages/settings.js` load;
- `processual_api/static/js/pages/settings.js` -> primary current client Settings behavior;
- `processual_api/static/js/app.js` -> Settings navigation plus dynamic loading of the Stage-18 Settings layout/operations assets;
- `processual_api/static/js/settings_layout_18.js` and `processual_api/static/css/settings_layout_18.css` -> active Settings layout behavior/style;
- `processual_api/static/js/settings_operations_18.js` and `processual_api/static/css/settings_operations_18.css` -> active Settings operational behavior/style.

All entries above except the explicitly deprecated alias are **ACTIVE / DO NOT DELETE** until composition is intentionally replaced.

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

The primary `pages/settings.js` uses the provider-connection API:

- `GET /settings/provider-connection`
- `PUT /settings/provider-connection/setup`
- `DELETE /settings/provider-connection/setup`
- `POST /settings/provider-connection/test`

It also uses the client-scoped usage summary:

- `GET /settings/client/usage-summary`

The current primary UI does **not** call the legacy `/settings/llm-provider*` paths and does **not** call `/settings/usage-summary`.

The Operations Center previously issued a second provider-status GET through `/settings/client/provider-connection`. That duplicate request has been removed. `settings_operations_18.js` now reuses the provider state rendered by the primary Settings surface and tracks subsequent changes with a targeted `MutationObserver`.

## Page readiness and output quality

The page currently exposes operational flows for:

- account/session identity;
- general preferences;
- subscription and billing status;
- usage/quota summary;
- Tunisia direct subscription preparation/payment workflow;
- BYOK provider setup, encrypted save, removal, and connection test;
- enterprise integration readiness;
- client self-service sandbox API-key issue/rotate/revoke;
- client requests, status timeline, admin follow-up, and supervisor messages;
- launch/readiness checklist and guided next actions.

Quality/safety properties verified in the current code and tests include:

- provider secrets are not returned by provider-status output;
- sandbox API keys expose raw key material once at creation/rotation and return only safe metadata afterwards;
- production/runtime connector permissions remain false for self-service sandbox keys;
- client usage summary is client-scoped;
- replacement provider endpoints are the current UI contract;
- active Settings JS/CSS assets are explicitly wired;
- top-up checkout contracts remain referenced by the active application service;
- page layout initialization is idempotent rather than relying on repeated delayed reconciliation;
- layout DOM reconciliation disconnects its observer while it moves/rewrites its own nodes, preventing self-triggered reconciliation loops;
- successful sandbox-key mutations update the local client state from the authoritative mutation response instead of immediately re-reading the same resources.

## Load and runtime findings

### Completed reductions

1. `settings_layout_18.js` previously ran reconciliation immediately and again at 100ms, 500ms, and 1500ms, in addition to a `MutationObserver`. The fixed timers were removed. Initialization is now idempotent, with late DOM changes handled by the observer/debounced reconciliation path.
2. The layout `MutationObserver` is now disconnected during `reconcile()` and reattached afterward. This prevents DOM moves/text adjustments performed by the reconciler itself from scheduling another reconciliation cycle.
3. `settings_operations_18.js` previously fetched provider status independently even though `pages/settings.js` already fetched and rendered the same state. The duplicate provider GET is removed; Operations now reuses the primary page state.
4. Operations Center previously performed a full `load()` after every successful sandbox-key create, rotate, or revoke. The mutation APIs already return enough authoritative information to update the local key list. Successful mutations now update local state directly; explicit Refresh remains available for user-requested resynchronization.
5. Operations Center previously loaded once inside `mount()` and again inside `init()`. Since `app.js` dynamically loads the asset and invokes `init()`, this could duplicate initial integration/key reads. `mount()` now owns the initial load and `init()` is idempotent mounting only.

### Remaining load opportunity

`pages/settings.js::loadClientSettings()` still loads several independent resources largely in sequence: account, base settings, subscription, usage summary, Tunisia payment option, API-key integration, and provider status. This is the largest remaining client-side latency optimization opportunity. It should be parallelized only after preserving current partial-failure behavior with explicit tests.

`refresh()` already overlaps `loadClientSettings()` with `loadClientRequests()`, so replacing that outer function with a superficial `Promise.all` is not expected to provide the main benefit. The sequencing to address is inside `loadClientSettings()`.

The Operations Center still needs its own detailed integration-profile payload because that information is not fully represented by the primary page DOM; this request is therefore not classified as duplicate yet.

## Internal legacy-code finding

`settings_subscription_runtime.py` actively replaces the legacy `GET /settings/subscription` route and then removes `_load_billing_subscriptions`, `_compute_stage`, and `get_subscription` from `processual_api.routers.settings` at composition time. This proves that those definitions inside the large `settings.py` module are legacy implementation code, even though the **runtime extension file itself is active and must not be deleted**.

This is a cleanup candidate for a later surgical refactor:

1. protect the authoritative runtime subscription route and plan-resolution behavior with direct tests;
2. remove the retired legacy definitions from `settings.py`;
3. simplify `retire_legacy_subscription_runtime()` so it no longer needs `delattr` cleanup;
4. run Settings CI and subscription/billing regression before considering any further file removal.

## Retirement candidates

These are candidates for staged retirement, not immediate deletion.

| Candidate | Current classification | Reason | Required next step before removal |
|---|---|---|---|
| legacy subscription definitions inside `routers/settings.py` (`_load_billing_subscriptions`, `_compute_stage`, legacy `get_subscription`) | **PROVEN RUNTIME-RETIRED INTERNAL CODE** | `settings_subscription_runtime.py` replaces the route and deletes these symbols at composition time | protect authoritative route ordering/behavior, then remove definitions surgically |
| `GET /settings/client/provider-connection` / `client_provider_alias_18.py` | **DEPRECATED COMPATIBILITY** | Operations Center no longer consumes it; direct provider endpoint is canonical | inventory external consumers and remove only after compatibility window |
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
- `settings_subscription_runtime.py`: authoritative runtime replacement for the legacy subscription implementation;
- `client_api_keys_18.py`: implements the self-service sandbox API-key actions used by Operations Center;
- `commercial_settings_top_up_checkout_contracts.py`: imported by the active top-up application service;
- `commercial_settings_top_up_ui_contracts.py`: imported by the checkout contract;
- `schemas/settings.py`: imported by the Settings router;
- `routers/settings.py`: included by `main.py`.

## Operational qualification matrix

| Area | Current state | Qualification evidence / remaining need |
|---|---|---|
| Main router wiring | QUALIFIED | regression test that main includes Settings router |
| Settings SPA wiring | QUALIFIED | index -> pages/settings.js and app -> Stage-18 asset guardrails |
| Browser JavaScript syntax | QUALIFIED IN SETTINGS CI | `node --check` for app/settings/layout/operations assets |
| Layout startup/load behavior | QUALIFIED | idempotent init + observer isolation + observer-based late reconciliation regression |
| Operations startup reads | QUALIFIED | mount owns one initial load; init no longer starts a duplicate load |
| Sandbox-key mutation reads | QUALIFIED | create/rotate/revoke update local state; no automatic post-mutation full reload |
| Provider connection | QUALIFIED / ACTIVE | API security, secret non-disclosure, setup/clear/test, current UI contract |
| Provider compatibility alias | DEPRECATED | retained only for compatibility; no current Operations UI dependency |
| Client usage summary | QUALIFIED / ACTIVE | authenticated-client isolation and UI contract tests |
| Subscription status | ACTIVE | authoritative subscription runtime is composed; direct route-ordering/removal tests should precede legacy-code deletion |
| API-key administration | ACTIVE | admin scope/RBAC, create/update/revoke regression |
| Client sandbox API keys | ACTIVE | fail-closed profile restrictions and safe one-time secret semantics; keep route extension in Settings CI |
| Client requests | ACTIVE | client isolation, admin review, status and supervisor-response regression |
| Integration readiness | ACTIVE | client/admin readiness regression |
| Supervisor session keys | ACTIVE | issuance/list/revocation and scope regression |
| General preferences | ACTIVE | persistence/default merge regression |
| Notifications | REVIEW REQUIRED | determine supported product use before keeping or retiring |
| Legacy LLM-provider endpoints | DEPRECATION CANDIDATE | external-consumer audit + shared-test helper extraction + compatibility window |
| Legacy usage-summary endpoint | DEPRECATION CANDIDATE | external-consumer audit + semantic replacement decision |
| File-backed Settings persistence | TECHNICAL DEBT / ACTIVE | corruption, atomic replace, backup, multi-process/storage-topology qualification |

## Dedicated Settings CI

`.github/workflows/settings-space.yml` is the focused gate for this subsystem. It covers:

- Settings Python/config/router/schema files;
- provider alias and sandbox API-key extension routers;
- active browser assets;
- Ruff on the Settings Python slice;
- Node 22 syntax checks for `app.js`, `pages/settings.js`, `settings_layout_18.js`, and `settings_operations_18.js`;
- Settings runtime/UI/security regression suites, including provider and load-behavior contracts.

This workflow is the required gate after each staged cleanup change.

## Persistence risk

Settings are currently stored in per-user JSON files under `processual_api/data` using a file lock, temporary file, backup, and atomic replacement. This is functional for the current topology but should not be assumed to provide cross-node shared persistence. Before horizontally scaling the Settings write path, production qualification must explicitly decide whether Settings remain node-local or move to a shared authoritative store.

No storage rewrite is authorized by this review alone.

## Staged cleanup plan

### Stage 0 — inventory and guardrails — COMPLETE

- Active composition and route extensions inventoried.
- Runtime wiring guardrail added.
- Dedicated Settings CI added.
- JavaScript syntax validation added.

### Stage 1 — load reduction and internal duplication — IN PROGRESS

- Fixed-delay layout reconciliation removed and initialization made idempotent.
- Observer self-reconciliation blocked.
- Duplicate Operations provider-status GET removed.
- Automatic post-key-mutation reloads removed.
- Duplicate Operations startup load removed.
- Next: protect partial-failure semantics and parallelize independent `loadClientSettings()` reads.
- Next: extract provider connection testing into one private/shared helper so `/provider-connection/test` no longer depends on the legacy endpoint function.
- Next: protect authoritative subscription route ordering, then remove runtime-retired subscription definitions from `settings.py`.

### Stage 2 — explicit endpoint deprecation — STARTED

- `/settings/client/provider-connection` alias marked deprecated after removing its current UI consumer.
- Next: audit external consumers.
- Then mark confirmed `/llm-provider*` and `/usage-summary` routes deprecated as appropriate.

### Stage 3 — first removals — NOT STARTED

- First preferred removal target is the proven runtime-retired subscription implementation **inside** `routers/settings.py`, after route-ordering tests are added.
- Remove only external legacy routes/files that have zero supported consumers after the compatibility window.
- Remove route-specific compatibility tests only when removal is intentional, replacing them with the canonical route contract where appropriate.
- Do not delete shared crypto/provider helpers that remain used by current paths.

### Stage 4 — file cleanup — NOT STARTED

- Re-run repository reference inventory.
- Delete files only when no runtime import, static load, test contract, migration, or supported compatibility requirement remains.
- One file or tightly coupled pair per change, followed by targeted tests and Settings CI review.

## Current decision

The Settings page is operationally substantial and its core page/API/task wiring is protected by a dedicated qualification gate. Five concrete load/churn reductions are now implemented, one compatibility endpoint has entered explicit deprecation without breaking callers, and one group of internal subscription functions has been proven runtime-retired.

No complete active Settings runtime file is currently justified for immediate deletion. The safest first code removal is the runtime-retired subscription implementation inside the large `settings.py` module, after adding authoritative route-ordering tests. The first likely **whole-file** deletion remains `client_provider_alias_18.py`, but only after its external compatibility window is closed.