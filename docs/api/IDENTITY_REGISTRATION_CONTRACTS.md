# Identity and Registration API Contracts

These contracts define the intended API surface. AUTH-R1 does not register the
routes and does not alter the existing `/auth/token` behavior.

## Public registration

### `GET /auth/registration/config`

Returns client-safe registration modes and password-policy hints. It never
returns internal roles, plan assignment controls, bootstrap state, or provider
configuration.

### `POST /auth/register`

Accepted fields:

```json
{
  "email": "user@example.com",
  "full_name": "Example User",
  "password": "a long passphrase",
  "accepted_terms_version": "2026-01"
}
```

### `POST /auth/register/organization`

Adds only `organization_name` to the individual-registration fields. The
server creates the owner membership; the request cannot supply a role, plan,
quota, scopes, client identifier, or organization identifier.

Both registration routes return the same safe response shape:

```json
{
  "status": "accepted",
  "next_action": "check_email"
}
```

The response remains generic when the normalized email already exists.

## Email verification

- `POST /auth/email/verify`
- `POST /auth/email/resend`

Action tokens are opaque, expiring, single-use, and persisted only as hashes.
Resending invalidates earlier unconsumed verification tokens.

## Login and session lifecycle

- `POST /auth/login`
- `POST /auth/refresh`
- `POST /auth/logout`
- `POST /auth/logout-all`
- `GET /auth/me`
- `GET /auth/sessions`
- `DELETE /auth/sessions/{session_id}`

Login accepts only `email` and `password`. The server derives every role,
organization, plan, and scope claim.

The access token claims are bounded to:

```text
sub, sid, org_id, membership_role, platform_role,
session_type, scopes, iat, exp, jti
```

Mutable subscription and quota state remains server-side and is not trusted
from JWT claims.

## Organization invitations

- `POST /organizations/current/invitations`
- `POST /organizations/invitations/accept`

Invitable roles are limited to:

```text
organization_admin, operator, auditor, viewer
```

Platform administration and organization ownership require separate governed
flows.

## Password lifecycle

- `POST /auth/password/forgot`
- `POST /auth/password/reset`
- `POST /auth/password/change`

Forgot-password responses are generic. A successful reset revokes existing
session families and invalidates earlier reset tokens.

## Permanently forbidden request fields

Public registration and login contracts reject:

```text
role, platform_role, membership_role, plan, plan_id, quota,
scopes, client_id, organization_id, is_admin, production_allowed
```

Unknown fields are rejected rather than ignored.
