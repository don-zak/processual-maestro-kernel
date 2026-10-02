# External Evaluation Workspace Hosting Architecture

**Decision date:** 2026-09-12  
**Qualified runtime baseline:** `6f7dd018737151cd1906be068f2478d02d19392b`

## Decision

The customer-facing Maestro product experience may expose External Evaluation from ZAXAM-TECH, but ZAXAM-TECH must not become the source of Evaluation authority.

The authority sequence remains:

`Policy / Authority → Admission → Execution → Evidence`

PostgreSQL-backed Maestro authority remains authoritative for grant/key state, admitted-execution quota, idempotency, revocation, runtime delivery and durable evidence.

## Phase 1 — isolated customer-facing embed

The first safe hosting step embeds the existing qualified Maestro External Evaluation Workspace inside the ZAXAM-TECH `maestro.html` page using a cross-origin iframe.

Target workspace:

`https://processual-maestro-external-evaluation.onrender.com/console/evaluation.html`

Security properties:

- the raw Evaluation API key is entered inside the Evaluation origin, not the ZAXAM parent page;
- ZAXAM-TECH does not proxy, persist, log or inspect the key;
- the iframe uses `referrerpolicy=no-referrer`;
- the iframe sandbox is limited to `allow-scripts allow-same-origin`;
- forms, popups and top navigation are not granted to the embed;
- the ZAXAM parent page contains no third-party script dependency for this integration;
- if the Evaluation workspace is unavailable, the experience fails closed and does not substitute a mock execution state;
- production execution remains disabled.

This phase avoids widening CORS or moving request construction into the marketing-site origin while providing a unified customer-facing Maestro page immediately.

## Phase 2 — native ZAXAM frontend

A later native frontend may replace the iframe only after an explicit origin contract is implemented and qualified.

Required controls before native migration:

1. explicit allowed-origin configuration for the intended ZAXAM origin;
2. no wildcard production CORS;
3. credential requests continue to use `credentials: omit` for Evaluation API-key flows unless a separately reviewed design requires otherwise;
4. raw Evaluation keys remain memory-only and are never written to localStorage/sessionStorage/IndexedDB/cookies/analytics;
5. no third-party analytics/session-replay script may observe the credential input or task input surface;
6. request URLs must be fixed/configured by trusted deployment configuration, never by user-controlled query parameters;
7. CSP/Referrer-Policy/Permissions-Policy must be defined for the native page;
8. the browser still cannot widen allowed tasks, bindings, endpoints, quota or production authority;
9. status reads remain +0 quota and execution admission semantics remain backend-controlled;
10. focused CORS/origin/browser security tests and live cross-origin verification must pass before rollout.

If a native migration changes authentication, admission, quota, idempotency, runtime or evidence semantics, reopen the affected Q1–Q10 qualification stages.

## Repository separation

The ZAXAM site change is maintained separately from the qualified kernel/runtime baseline.

- Kernel/runtime repository: `don-zak/processual-maestro-kernel`
- ZAXAM site repository: `don-zak/ZAXAM-TECH.blog`

The ZAXAM integration should be reviewed and merged through its own PR. Do not couple site presentation rollout to a blind merge of the large kernel qualification PR.

## Acceptance criteria for Phase 1

- Maestro page visibly contains the real External Evaluation Workspace;
- the workspace URL is the dedicated Evaluation origin;
- credential entry occurs inside that origin;
- parent page has no storage or proxy path for the Evaluation key;
- iframe sandbox/referrer restrictions are regression-tested;
- GitHub Pages verification passes;
- deployment to site `main` remains a separate explicit merge action;
- kernel PR remains Draft until its independent release gates are satisfied.
