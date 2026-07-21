# AUTH-R3 credential, token, and TOTP cryptography

AUTH-R3 supplies pure cryptographic services. It does not expose public routes,
write database rows, send email, or activate a user session.

## Passwords

Passwords use Argon2id with a minimum 64 MiB memory cost, three iterations, a
16-byte salt, and a 32-byte result. Verification returns only validity and
whether the encoded hash should be upgraded. Malformed hashes fail closed.

## Opaque tokens and recovery codes

Action tokens, refresh tokens, challenge handles, and recovery codes are
generated from the operating system CSPRNG. Persistence uses HMAC-SHA-256 with
a minimum 32-byte server pepper and purpose-specific domain separation. Raw
material exists only long enough to deliver it to the intended user or cookie.

Recovery codes are human-readable, independently random, single-use values.
Only their HMAC digest may be written to `auth_mfa_recovery_codes`.

## TOTP

TOTP follows RFC 6238 with SHA-1, six digits, and a 30-second period for broad
authenticator compatibility. Verification permits at most a two-step window.
The service returns the matched time step so the transaction can atomically
reject a step that is not newer than `last_used_step`.

## TOTP seed encryption

TOTP seeds require recovery during verification, so they cannot be one-way
hashed. AUTH-R3 protects them with AES-256-GCM. The authenticated additional
data binds ciphertext to both user and factor identifiers. Stored material is
the nonce-prefixed ciphertext and a non-secret key-version reference.

Production keys must be supplied by a secret manager or KMS-backed envelope
system. They must never be committed, logged, returned by an API, or stored in
the same database row as the ciphertext. The key ring supports decrypting an
old version and re-encrypting under the current version.

## Failure behavior

- wrong passwords, malformed hashes, invalid tokens, and invalid TOTP codes do
  not disclose which internal check failed;
- ciphertext tampering or AAD mismatch fails authentication;
- missing key versions fail closed;
- TOTP replay is rejected even inside the accepted clock window;
- SMS is not introduced as an authentication factor.
