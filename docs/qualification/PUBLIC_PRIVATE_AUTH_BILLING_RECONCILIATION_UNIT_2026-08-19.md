# Public / Private Auth + Billing Reconciliation Unit — 2026-08-19

**Public main:** `a63b4a7d40643a685caeaafc8cbfd11f59e9d544`  
**Private main:** `84e3354cd43802176ee93ed94f72144341c0068b`  
**Status:** **MAJOR PARITY PORT REQUIRED — PRIVATE MAIN UNCHANGED**

## Executive finding

The private repository is not merely a public baseline plus private integrations for the `processual_api/auth` and `processual_api/billing` surfaces. It is materially older.

The public repository contains the later qualified authentication, commercial, quota, pricing, checkout and billing authority architecture. The private repository still contains compact legacy routers from an earlier product stage.

Therefore these surfaces must not be reconciled by patching individual functions. They require a controlled public-core parity port with preservation of any intentional private integration hooks.

## 1. Authentication drift

### Private tree

Private `processual_api/auth/` contains only:

- `__init__.py`
- `router.py`
- `security.py`

The private router implements the older compact surface:

- username/password `/auth/token`;
- direct API-key generation;
- `/auth/me`.

### Public tree

Public `processual_api/auth/` contains the full later authentication program, including families for:

- account recovery contracts/repository/runtime/router/service;
- external authority revocation;
- encrypted delivery contracts/crypto/repository/dispatcher/runtime/worker;
- protected delivery operations;
- recovery-email lifecycle;
- email verification;
- MFA contracts/crypto/repository/runtime/router/service;
- registration contracts/repository/runtime/router/service;
- organization authority;
- platform administrator bootstrap;
- platform supervisor authority;
- rate limiting;
- sessions and identity runtime;
- password and token security;
- operational recovery/security controls.

This aligns with the separately retained AUTH-R10 readiness evidence that records the later authentication program as qualified.

### `security.py`

Private and public both retain a `security.py`, but public has evolved substantially. The public security surface includes dynamic API-key verification, supervisor session keys, admin audit projection, organization/session/platform authorities and expanded JWT claims. It is not safe to preserve private `security.py` as the authoritative implementation merely because the filename matches.

Disposition: **PUBLIC AUTH CORE PORT REQUIRED**, followed by semantic reconciliation of any private callers and compatibility routes.

## 2. Billing/commercial drift

### Private tree

Private `processual_api/billing/` contains only:

- `__init__.py`
- `router.py`

The legacy private router directly:

- reads Lemon Squeezy credentials/variant IDs from environment;
- calls Lemon Squeezy checkout/customer APIs;
- verifies webhook signatures inside the router;
- persists checkout/subscription state to JSON files under `processual_api/data`;
- exposes checkout/portal/webhook behavior from one monolithic route module.

### Public tree

Public `processual_api/billing/` contains the later commercial architecture, including:

- commercial catalog/contracts/state-machine/event models;
- quota top-up contracts/application service/repositories/UoW/audit;
- direct checkout router;
- customer billing authority and immutable statements;
- subscription catalog/preparation;
- plan capability routes;
- offer pricebook/fulfillment policy;
- Maestro Units, calibration, shadow measurements and evidence;
- pricing review/selected pricing;
- public plan-led registration journey;
- commercial execution identity/authority/readiness;
- additional governed billing/commercial services.

The public billing router is no longer the source of commercial truth. It composes authoritative services and the secure Lemon Squeezy webhook path from `processual_api/admin_marketplace`.

Disposition: **PUBLIC BILLING/COMMERCIAL CORE PORT REQUIRED**. The old private monolithic router must not remain an alternate authority path after reconciliation.

## 3. Security implication

Keeping the legacy private routers alongside the later public authority model without explicit compatibility controls would create duplicate authority paths.

Examples of unacceptable outcomes:

- legacy auth token/API-key issuance bypassing later identity authority;
- direct private Lemon Squeezy checkout bypassing channel eligibility, offer, entitlement or activation gates;
- legacy webhook handling activating state outside the secure inbox/reconciliation lifecycle;
- local JSON persistence becoming an alternate source of truth beside governed SQL persistence;
- role/scope semantics diverging between public and private runtime.

Reconciliation must fail closed against these split-authority conditions.

## 4. Required port strategy

### Authentication

1. Port the complete qualified public auth module set, not selected files.
2. Port corresponding migrations, settings, middleware and tests.
3. Reconcile `processual_api/main.py` router registration after auth files exist.
4. Inventory private code importing legacy `auth.router` or assumptions from legacy `security.py`.
5. Preserve a compatibility shim only if a caller genuinely requires it and only when it delegates to the new authority rather than issuing independent authority.
6. Run focused auth regression and the private full suite.

### Billing/commercial

1. Port the public billing module set together with required Admin Marketplace dependencies.
2. Port required commercial/quota/pricing migrations and tests.
3. Replace legacy direct checkout/webhook authority with the governed public services.
4. Inventory any private integrations that consume legacy JSON checkout/subscription artifacts.
5. Migrate or explicitly retire that storage contract; do not silently maintain two active sources of truth.
6. Verify public/private checkout, webhook, subscription, entitlement and quota boundaries.

## 5. Dependency ordering consequence

Because public billing now imports Admin Marketplace secure webhook/subscription services, private reconciliation cannot safely port `billing/` before its required shared `admin_marketplace/` surface is also present.

Recommended next order becomes:

1. kernel port unit;
2. cgtlib shared-core port unit;
3. auth complete parity unit;
4. Admin Marketplace shared surface;
5. billing/commercial shared surface;
6. migrations;
7. `main.py`, middleware and settings reconciliation;
8. private integrations compatibility pass;
9. CI/build/package reconciliation.

## 6. Current authority

- classification only; no private code port applied;
- private `main` unchanged;
- no legacy private authority path has been declared production-safe;
- no merge performed;
- no staging or production authority granted;
- real-environment proof backlog remains mandatory.