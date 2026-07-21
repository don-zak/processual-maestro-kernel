# AUTH-R2 identity, session, and 2FA data model

AUTH-R2 introduces the PostgreSQL authority required by the AUTH-R1 contracts.
It remains runtime-neutral: no public registration, login, refresh, or 2FA route
is enabled by this increment.

## Authoritative records

- `identity_users` stores normalized identity data and an Argon2id encoded hash.
- `identity_organizations` and `identity_memberships` establish tenant boundaries.
- `auth_sessions` owns authenticated session state and refresh-token families.
- `auth_refresh_tokens` stores only token hashes and rotation/reuse timestamps.
- `auth_action_tokens` stores only hashes for verification, reset, change-email,
  and invitation actions.

## Two-factor authentication

The first supported factor is TOTP from an authenticator application. SMS is
not an authentication factor in this design because telephone numbers are
susceptible to reassignment and SIM-swap attacks.

`auth_mfa_factors` stores the TOTP seed only as authenticated ciphertext plus a
key-version reference. A TOTP seed cannot be one-way hashed because the server
must recover it to verify a code. Encryption and key rotation are implemented
in AUTH-R3; plaintext seeds must never be committed or persisted.

`last_used_step` prevents accepting the same TOTP time step twice.
`auth_mfa_recovery_codes` stores one-way hashes only and records single use.
`auth_mfa_challenges` stores a hash of the short-lived challenge handle, its
attempt count, expiry, and terminal status. Later services must rate-limit both
challenge creation and verification.

The factor table deliberately identifies the factor type so WebAuthn can be
added in a separate migration. AUTH-R2 restricts the accepted value to `totp`.

## Isolation and authority rules

- Organization roles exist only on memberships; they are never accepted from
  registration or login payloads.
- Membership uniqueness prevents duplicate authority edges for one user and
  organization.
- A session may be scoped to an organization but always belongs to one user.
- Revoking a refresh family is represented by revoking the owning session and
  its token rows in one database transaction.
- Redis may accelerate rate limiting but cannot replace these PostgreSQL rows.

## Migration policy

The first Alembic revision creates only identity and authentication tables.
The downgrade removes them in reverse dependency order. Deployment must run
`alembic upgrade head` as an explicit release step before AUTH routes are
enabled.
