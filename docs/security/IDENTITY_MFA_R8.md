# AUTH-R8 identity MFA and step-up

AUTH-R8 adds an authoritative TOTP second factor to PostgreSQL identity
sessions. TOTP seeds are generated with 160 bits of entropy and encrypted with
AES-256-GCM under a dedicated, versioned MFA key ring. Associated data binds
each ciphertext to its factor, user, and factor type. Raw seeds are returned
only during enrollment and must never be logged.

Enrollment remains pending until a valid TOTP code is confirmed. Confirmation
activates the factor, records the accepted TOTP step, marks the current session
as MFA-satisfied, and returns a new set of recovery codes once. Only HMAC
digests of recovery codes are stored. Recovery codes are consumed atomically
and cannot be replayed.

TOTP verification accepts a bounded one-step clock window. A factor's
`last_used_step` prevents the same or an older step from being accepted again,
including concurrent retries serialized by the database row lock. Redis adds
per-IP and per-user verification limits and fails closed when unavailable.

Users with an active factor, organization owners, and organization
administrators receive an identity session restricted to the `auth:mfa` scope
until the authoritative session row has `mfa_satisfied_at`. Client JWT claims
cannot bypass this check. Normal evaluation authority is restored only after a
successful TOTP or one-time recovery-code verification.

Disabling MFA and regenerating recovery codes require a recent step-up proof.
Disabling a factor removes its recovery codes and revokes the user's other
sessions. The reusable `require_recent_mfa` dependency protects future
administrative and commercial mutations without coupling those features to
the MFA implementation.

Production requires `AUTH_MFA_KEY_RING_JSON` and
`AUTH_MFA_CURRENT_KEY_VERSION`. MFA keys must be independent from delivery
encryption keys and managed through the deployment secret manager. Key
rotation retains old versions for decryption while new enrollments use the
current version.
