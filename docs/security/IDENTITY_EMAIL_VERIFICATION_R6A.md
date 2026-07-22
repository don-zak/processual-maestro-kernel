# AUTH-R6A email verification and resend

AUTH-R6A adds `POST /auth/verify-email` and
`POST /auth/verification/resend`. It does not send email directly; it rotates
the verification action token and writes a new encrypted delivery outbox row in
the same PostgreSQL transaction. Delivery claiming, provider calls, retry, and
dead-letter behavior remain isolated to AUTH-R6B.

Verification hashes the presented token with the purpose-separated token
pepper, locks the matching action token and user, and consumes a valid token
once. Expired, consumed, invalidated, missing, and otherwise ineligible tokens
receive the same processed response. The raw token is never stored or audited.

Resend returns the same accepted response for missing, active, limited, and
pending accounts. A locked pending-user row serializes rotations. An active
token younger than 60 seconds suppresses duplicate issuance. Otherwise all
active verification tokens are explicitly invalidated and the replacement
token plus encrypted outbox row are committed together.

Both routes use the dedicated Redis rules already defined for verification and
resend, trusted-proxy client-IP resolution, the registration response-time
floor, generic fail-closed dependency errors, and coarse audit fields that omit
email addresses, IP addresses, tokens, digests, and ciphertext.
