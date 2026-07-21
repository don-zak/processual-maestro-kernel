# AUTH-R4 transactional registration service

AUTH-R4 adds application services for individual and organization registration.
It does not add public HTTP routes, email transport, sessions, or UI.

## Transaction boundary

One database unit of work creates the pending user, immutable terms acceptance,
hash-only email-verification action token, and—when requested—the pending
organization plus its server-derived owner membership. A uniqueness race rolls
back the whole transaction.

## Enumeration resistance

The service returns the same public receipt for a newly accepted email, an
existing email, and a uniqueness race. Password hashing and verification-token
generation occur before the existence lookup to reduce obvious timing
differences. Rate limiting and response-time padding remain HTTP-layer duties.

The internal delivery object is separate from the public receipt. It contains
the raw verification token only for a newly committed registration so a later
mail dispatcher can deliver it once. Only its HMAC digest is persisted.

## Authority boundaries

- only individual and organization self-service modes are accepted;
- platform-admin bootstrap and invitations cannot enter this service;
- an individual request cannot inject organization data;
- organization-owner membership is assigned by the server, never the client;
- users remain `pending_verification` and organizations remain
  `pending_review` until later governed flows advance them;
- registration creates no authenticated session.

## UI acceptance carried forward

Future registration, verification, login, recovery, and 2FA cards must use the
existing application design system and match current page/card quality,
responsive behavior, interaction states, accessibility, and bilingual layout.
