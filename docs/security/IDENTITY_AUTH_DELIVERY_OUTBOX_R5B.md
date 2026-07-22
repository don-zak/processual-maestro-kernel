# AUTH-R5B encrypted transactional delivery outbox

AUTH-R5B adds the persistence boundary required between atomic registration and
later email delivery. It does not add public HTTP routes or an email provider.

## Atomic boundary

The pending user, terms acceptance, verification-token HMAC digest, optional
organization and owner membership, and one delivery-outbox row are committed
by the same SQLAlchemy unit of work. A uniqueness conflict rolls back every
row. An existing normalized email creates neither a token nor an outbox row.

## Secret boundary

The opaque verification token is never returned by `RegistrationService` and
is never stored as plaintext. `DeliveryPayloadCipher` encrypts it with
AES-256-GCM before the existence lookup. The authenticated associated data
binds the ciphertext to the outbox row, user, action token, and purpose.

The outbox row stores only:

- server-owned UUID references;
- the event type;
- nonce-prefixed authenticated ciphertext and key-version reference;
- availability, claim, attempt, delivery, and bounded error state.

It does not duplicate the email address. A later dispatcher must resolve the
recipient through the server-owned user relationship and decrypt only at the
provider boundary.

## Operational boundary

The encryption key is not stored in PostgreSQL. Runtime wiring must inject a
versioned key ring from the approved secrets authority. Missing keys, database
failure, or inability to persist the outbox are fail-closed conditions for a
new registration. Provider downtime after commit does not roll back the user;
the pending outbox row remains available for bounded retry.

Dispatcher claiming, retry policy, provider integration, and public HTTP
registration adapters remain later controlled increments.
