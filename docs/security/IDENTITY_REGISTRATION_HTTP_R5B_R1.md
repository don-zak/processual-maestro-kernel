# AUTH-R5B-R1 registration HTTP adapter

AUTH-R5B-R1 exposes `GET /auth/registration/config`, `POST /auth/register`, and
`POST /auth/register/organization`. It does not alter the legacy `/auth/token`
contract and it does not add login, verification, sessions, or email dispatch.

## Runtime authorities

Registration fails closed unless PostgreSQL has been initialized, Redis is
available for the authoritative rate-limit decision, and all cryptographic
material is valid. Deployments must supply:

- `AUTH_TOKEN_PEPPER`: at least 32 bytes of unique secret material.
- `AUTH_RATE_LIMIT_PEPPER`: a different secret of at least 32 bytes.
- `AUTH_DELIVERY_KEY_RING_JSON`: a JSON object mapping key versions to
  base64-encoded 32-byte AES keys.
- `AUTH_DELIVERY_CURRENT_KEY_VERSION`: a version present in that key ring.
- `AUTH_TRUSTED_PROXY_CIDRS`: only the real ingress/proxy CIDRs; wildcard
  networks are rejected.
- `AUTH_TRUSTED_PROXY_MAX_HOPS`: bounded forwarded-chain length (default 8).
- `AUTH_REGISTRATION_MIN_RESPONSE_MS`: response-time floor from 0 to 5000 ms
  (default 350 ms).

These values belong in the deployment secret/config authority and must never be
committed. Token, rate-limit, and delivery secrets are purpose-separated.

## Enumeration and failure behavior

The route consumes IP rules before normalizing and consuming the email rule.
An IP rejection returns `429` with `Retry-After`. An email rejection returns the
same generic `202` body as an accepted or already-existing email and does not
call PostgreSQL. Missing Redis, PostgreSQL, or delivery authority returns a
generic `503` and performs no registration write.

Request validation is sanitized so passwords and rejected authority fields are
not reflected in a `422` response. Audit records contain only the correlation
ID, server-selected registration mode, and coarse result; they do not contain
email addresses, IP addresses, passwords, action tokens, or ciphertext.

The registration service continues to write the identity, terms acceptance,
hashed verification token, optional organization ownership, and encrypted
delivery outbox row in one PostgreSQL transaction. Email is never sent inside
that transaction.
