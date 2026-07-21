# ADR: Identity, Registration, and Browser Sessions

- Status: accepted for AUTH-R1 implementation
- Baseline: `b72375cf09d5bbb02e292ba8e3ca8eacaf5e8ade`
- Contract: `identity_registration_r1`
- Runtime impact in this change: none

## Context

The current `/auth/token` route authenticates both the platform administrator
and the client UI from one configured credential pair. The request also chooses
the requested role. This is suitable only for the bounded development gateway;
it is not an identity system and must not become the production registration
path.

Maestro needs real users, organizations, memberships, revocable sessions, and
tenant isolation before quotas, pricing, or an operational dispatcher can be
trusted.

## Decision

1. Registration is hybrid:
   - individual and ordinary organization registration are self-service;
   - invitations add members to an existing organization;
   - enterprise and regulated organizations begin with an reviewed application;
   - platform administrators are never created through public registration.
2. Email verification is mandatory before a full session is issued.
3. The server derives roles, organization context, plans, and scopes. Login and
   registration requests cannot select them.
4. PostgreSQL is authoritative for users, memberships, sessions, revocations,
   and one-time action tokens.
5. Redis supports rate limiting and cache acceleration only. Loss of Redis must
   not make a revoked session valid.
6. User passwords use Argon2id through a password-specific component. API-key
   hashing remains a separate concern.
7. Browser access tokens are short-lived and memory-only. Rotating refresh
   tokens are stored in Secure, HttpOnly, SameSite cookies; only token hashes
   are persisted.
8. Refresh-token reuse revokes its entire session family.
9. Cookie-backed state-changing requests require CSRF protection.
10. Existing API keys and supervisor session keys remain independent
    authentication mechanisms.

## Registration outcomes

| Mode | Server-created membership | Review |
| --- | --- | --- |
| Individual | owner of a personal workspace | no |
| Organization | owner of the new organization | no |
| Invitation | invited organization role | inviter-controlled |
| Enterprise application | owner after approval and invitation | required |
| Platform admin bootstrap | platform administrator | deployment-only |

Organization ownership is never assigned by a normal invitation. It requires a
separate, audited transfer flow.

## Compatibility strategy

- The configured administrator credential remains a temporary bootstrap path.
- It cannot authenticate a client after the identity runtime is enabled.
- The current `client_id` claim is retained temporarily but becomes a
  server-derived compatibility alias for `organization_id`.
- Stage 18 resources remain default-deny and become organization-scoped in a
  later compatibility PR.
- No JSON store is migrated implicitly by the registration work.

## Consequences

- Alembic migrations and PostgreSQL-backed repositories are required before
  public registration routes are enabled.
- A mail delivery abstraction is required, with a non-network development
  backend and an explicit production backend.
- The frontend must stop persisting bearer access tokens in Web Storage.
- Existing auth regression tests remain until the compatibility transition is
  complete.

## Out of scope

- billing and checkout;
- 24/7 quota accounting;
- enterprise SSO;
- WebAuthn;
- operational sandbox dispatch;
- production or write-scope enablement;
- CGT equations or Fate Engine changes.
