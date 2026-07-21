# Identity and Registration Threat Model

## Protected assets

- password hashes;
- email-verification and password-reset authority;
- browser sessions and refresh-token families;
- organization membership and role assignments;
- platform-administrator authority;
- organization-scoped Stage 18 resources;
- audit evidence without raw credentials.

## Trust boundaries

1. Anonymous browser to public auth routes.
2. Auth routes to PostgreSQL repositories.
3. Auth routes to the mail-delivery adapter.
4. Auth routes to Redis rate-limit state.
5. Browser refresh cookie to the session-rotation service.
6. Authenticated identity to organization-scoped application routes.
7. Deployment bootstrap to platform-administrator creation.

## Threats and mandatory controls

| Threat | Mandatory control |
| --- | --- |
| Account enumeration | generic registration, reset, and resend responses |
| Duplicate-email race | normalized unique database constraint |
| Password disclosure | Argon2id; never log or persist raw passwords |
| Verification-token theft | short lifetime, hash-only storage, one-time use |
| Refresh-token database leak | hash-only storage and session-family rotation |
| Refresh-token replay | reuse detection and family revocation |
| Session fixation | server-generated session identifiers after authentication |
| Browser token theft | memory-only access token; HttpOnly refresh cookie |
| CSRF | SameSite cookie plus explicit CSRF validation |
| Brute force | per-account and per-origin rate limits plus temporary lock |
| Role escalation | server-derived role; request schemas forbid role and plan |
| Tenant confusion | server-derived organization context on every protected route |
| Invitation theft | email-bound, expiring, one-time invitation token |
| Last-owner removal | transactional last-owner invariant |
| Stale privilege | revoke or refresh sessions after membership changes |
| Redis loss | PostgreSQL remains authoritative for session validity |
| Mail outage | durable delivery intent and safe retry; no partial activation |
| Audit leakage | redact passwords, tokens, cookies, and authorization headers |

## Abuse cases required in tests

- two simultaneous registrations for the same normalized email;
- login request containing a client-selected role or plan;
- expired, consumed, revoked, or replayed action token;
- refresh-token replay after successful rotation;
- cross-organization resource access using path and body manipulation;
- invitation accepted by a different normalized email;
- organization administrator attempting to grant platform administrator;
- removal of the final active organization owner;
- membership downgrade followed by use of an old session;
- Redis unavailable while a session is revoked in PostgreSQL;
- secrets included in exception messages, audit logs, or browser evidence.

## Security gates before enabling public registration

- database migration up/down proof;
- tenant-isolation matrix passed;
- registration and reset enumeration tests passed;
- refresh rotation and replay tests passed;
- CSRF tests passed;
- secret and log scans passed;
- authenticated browser proof passed;
- production startup rejects incomplete auth configuration.
