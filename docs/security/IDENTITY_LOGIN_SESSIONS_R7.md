# AUTH-R7 identity login and sessions

AUTH-R7 adds the production identity-session path while retaining the legacy
deployment-admin `/auth/token` bootstrap route. Its client-role compatibility
mode remains development-only and is rejected in production. Clients log in with a normalized
email and password only; they cannot select roles, scopes, plans, organizations,
or administrative authority.

Password verification uses Argon2id. Unknown accounts execute the same
password-verification backend against a process-cached dummy hash. Redis applies
hashed IP and normalized-email limits before login, while PostgreSQL tracks a
bounded failed-login counter and temporary lockout. Dependency failure is
fail-closed and public errors do not distinguish missing, pending, disabled,
locked, or incorrectly authenticated accounts.

Successful login creates an authoritative PostgreSQL session and stores only an
HMAC digest of a random refresh token. The short-lived access token contains a
session identifier. Identity bearer authentication rechecks that session and
the active user in PostgreSQL, so logout and revocation take effect immediately
even before the access token expires.

Refresh tokens rotate on every use. Replaying a consumed token marks reuse and
revokes the entire session family. Refresh and cookie-backed logout operations
require a strict double-submit CSRF value. The refresh cookie is Secure,
HttpOnly, SameSite=Strict, and scoped to `/auth/session`; the CSRF cookie is
Secure and readable only so the client can copy it into `X-CSRF-Token`.

The API returns access tokens in JSON for memory-only client storage. It never
returns refresh tokens in JSON and never logs emails, passwords, raw refresh
tokens, CSRF values, or bearer tokens. Users can list active sessions and revoke
one session through an authoritative identity bearer token, or revoke all
sessions through the protected refresh-cookie flow.
