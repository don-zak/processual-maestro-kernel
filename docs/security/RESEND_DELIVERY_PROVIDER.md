# Resend authentication delivery provider

Processual Maestro can use Resend for authentication and account-recovery email delivery by setting `AUTH_DELIVERY_PROVIDER_KIND=resend`.

## Required deployment authority

Set the following values only in the deployment secret/configuration manager:

- `AUTH_RESEND_API_KEY` — secret API authority used by the delivery worker only.
- `AUTH_RESEND_SENDER_EMAIL` — verified sender identity or address authorized by the selected Resend account/domain.
- `AUTH_PUBLIC_BASE_URL` — public Maestro authority base URL used to construct verification and recovery links.

Never commit `AUTH_RESEND_API_KEY`, recovery tokens, verification URLs, or provider responses containing sensitive material.

## Runtime boundary

The web authority writes encrypted delivery payloads to the authentication outbox. The separate delivery worker claims rows, decrypts only the bounded payload required for delivery, and sends the message through Resend's HTTPS email API. The worker remains the only component that receives the provider API key.

Resend requests use an `Idempotency-Key` derived from the outbox delivery identity so a retry does not intentionally create duplicate email side effects. Provider failures are reduced to bounded internal classifications such as `provider_4xx`, `provider_rate_limited`, `provider_5xx`, `provider_timeout`, or `provider_network`; provider secret values and recovery URLs must not be included in those exceptions.

## Fail-closed behavior

The Resend runtime must refuse to initialize when the API key or sender identity is absent/invalid. The release gate also rejects an unsupported delivery kind and incomplete Resend authority. Do not fall back automatically from Resend to another provider when Resend is explicitly selected.

## Operational qualification

Before production use, prove the following sequence on the deployed exact head:

`recovery start -> encrypted outbox -> worker claim -> Resend accepted -> delivered -> recovery completion`

Also verify that logs and persisted evidence contain no raw API key, recovery token, full recovery URL, or raw provider response.
