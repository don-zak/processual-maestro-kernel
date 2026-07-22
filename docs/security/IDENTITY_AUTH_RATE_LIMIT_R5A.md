# AUTH-R5A identity rate-limit authority

AUTH-R5A adds the Redis-backed authority that registration, email verification,
password recovery, login, and TOTP routes will call. It does not expose a new
HTTP route by itself.

## Atomic multi-window decisions

Every action evaluates all applicable rules in one Redis Lua invocation. The
script increments each counter, sets its TTL on first use, and returns a single
allow or reject decision. Concurrent processes and multiple Cloud Run instances
therefore share the same decision authority.

The default registration policy combines short and daily IP limits with a
separate normalized-email limit. Organization registration is stricter. Email
resend and verification use their own independent windows.

## Data minimization

Redis keys contain only HMAC-SHA-256 digests produced with a dedicated secret
pepper and purpose-separated input. Raw IP addresses, normalized emails, and
verification tokens never appear in keys. The pepper must contain at least 32
bytes and must come from the production secret manager.

## Proxy trust

`X-Forwarded-For` is ignored unless the direct peer belongs to an explicitly
configured trusted CIDR. Trusted chains are walked from the application side
toward the client, and the first untrusted address becomes the client identity.
Malformed, empty, or excessive chains fall back to the direct peer.

Cloud Run deployments must configure only the actual ingress/proxy ranges; a
wildcard trusted range is forbidden operationally.

## Failure behavior

Redis is the authority for identity rate limits, not for sessions. A missing,
failed, or malformed Redis decision raises `AuthRateLimitUnavailableError`. Public
identity write routes must translate that failure to a generic 503 and must not
continue the protected operation.

Email- or token-specific throttling remains internal. HTTP adapters must keep
enumeration-sensitive responses generic and expose `Retry-After` only for an
IP-wide rejection that is safe to disclose.

## Scope boundary

AUTH-R5B will wire this authority into registration and email-verification HTTP
adapters. Login, recovery, session rotation, and TOTP challenge endpoints will
reuse the same primitive in later increments with action-specific rules.
