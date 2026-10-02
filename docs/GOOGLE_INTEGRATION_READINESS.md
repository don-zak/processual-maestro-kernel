# Google Integration Deployment-Time Readiness

## Scope

This qualification separates two different Google integration classes and does not claim a live production connection.

1. **Gemini provider access** — server-to-server Gemini API access through the existing `GeminiAdapter`.
2. **Google user-data OAuth** — a future connector class for Google APIs that require end-user OAuth consent.

They must not be treated as the same credential or authority path.

## Gemini provider contract

Current implementation:

- adapter boundary: `processual_api/cgt_governor/adapters/gemini_adapter.py`
- SDK dependency: `google-genai`
- server-side credential environment variable: `GEMINI_API_KEY`
- optional model selection: `GEMINI_DEFAULT_MODEL`
- no provider credential is bundled with the repository
- the adapter reports not configured when the key is absent
- generation fails closed when `GEMINI_API_KEY` is absent
- the key is supplied to the server-side SDK client and is not exposed to browser code

Deployment requirements:

- provision a currently supported, restricted Gemini credential through the deployment secret system
- do not commit the credential to Git, configuration examples, test fixtures, logs, or evidence
- use a dedicated Google project/credential appropriate to the deployment environment
- verify provider billing/quota separately from Maestro runtime authority
- rotate/revoke the provider credential outside the repository when compromised

The production example environment intentionally contains an empty `GEMINI_API_KEY=` placeholder only.

## Google OAuth connector contract

No Google user-data OAuth connector is currently claimed by this repository. In particular, the Gemini adapter does not require an OAuth callback route and must not be used as evidence that Google OAuth is implemented.

If a future Google connector requires user authorization, readiness requires all of the following before it may be enabled:

- a dedicated adapter/connector boundary for the target Google API
- explicit minimum required scopes
- separate testing and production Google Cloud projects/clients
- server-controlled OAuth client configuration
- client secret stored only through the deployment secret system
- an HTTPS redirect URI on an owned/verified domain for production
- state/CSRF protection and authorization-code correlation
- fail-closed callback handling for invalid state, code, audience, issuer, or redirect context as applicable
- encrypted or externalized token storage; no refresh/access token in browser storage, logs, evidence, or repository files
- refresh/revocation handling
- disconnect/revoke operation
- test/mock wiring that does not require production credentials
- deployment and operator runbook updates
- any Google verification/consent-screen requirements applicable to the selected scopes

Until those artifacts exist for a specific Google API, the correct state is **not configured / not enabled**, not partially authorized.

## Authority boundaries

Google credentials do not become Maestro commercial or execution authority.

- Maestro/PostgreSQL remains authoritative for Maestro grants, Evaluation API keys, quota, revocation, and execution admission.
- A Google credential authorizes only the bounded external provider operation for which it was provisioned.
- Render evaluation sandbox remains an execution target and must not hold or decide Maestro authority.

## Qualification checklist

### Current Gemini path

- [x] adapter boundary exists
- [x] environment-variable credential contract exists
- [x] credential example is empty
- [x] missing credential is fail-closed
- [x] SDK dependency is declared
- [x] provider call is server-side
- [x] no production Google credential is required for CI qualification
- [ ] deployment-time supported credential provisioned
- [ ] live non-production provider smoke test performed with deployment-owned secret
- [ ] production billing/quota/monitoring configured when production is authorized

### Future OAuth path

- [ ] target Google API and minimum scopes selected
- [ ] connector boundary implemented
- [ ] test/prod Google projects separated
- [ ] OAuth client configuration externalized
- [ ] HTTPS callback implemented and registered
- [ ] state/code validation tested
- [ ] token storage/refresh/revocation implemented
- [ ] disconnect operation implemented
- [ ] no-secret/no-token leakage tests green
- [ ] deployment runbook and provider verification requirements completed

## Readiness disposition

**Gemini:** code/configuration ready for deployment-time credential binding; live provider access is an operational step and is not claimed here.

**Google OAuth:** intentionally not claimed as implemented. It becomes a separate qualification item only when a concrete Google API requiring user OAuth is selected.
