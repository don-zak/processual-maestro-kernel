# Gmail API authentication delivery provider

Processual Maestro can use Gmail API for transactional authentication delivery such as account recovery and recovery-email verification.

## Provider selection

Set:

```text
AUTH_DELIVERY_PROVIDER_KIND=gmail_api
```

The existing HTTP provider remains available with `AUTH_DELIVERY_PROVIDER_KIND=http`.

## Required Gmail settings

Non-secret settings:

```text
AUTH_GMAIL_CLIENT_ID=
AUTH_GMAIL_SENDER_EMAIL=
```

Secrets:

```text
AUTH_GMAIL_CLIENT_SECRET=
AUTH_GMAIL_REFRESH_TOKEN=
```

Keep `AUTH_GMAIL_CLIENT_SECRET` and `AUTH_GMAIL_REFRESH_TOKEN` in the deployment secret manager. Never commit OAuth client secrets, refresh tokens, access tokens, recovery links, or recovery tokens to the repository or logs.

The OAuth refresh token must be issued to the Gmail account used as `AUTH_GMAIL_SENDER_EMAIL` with the narrow Gmail API scope:

```text
https://www.googleapis.com/auth/gmail.send
```

The delivery worker exchanges the refresh token for a short-lived access token at runtime and sends through Gmail API. Processual Maestro does not persist the access token.

## Existing delivery safeguards

The Gmail provider preserves the existing authentication-delivery outbox boundary:

```text
Auth request -> encrypted PostgreSQL outbox -> delivery worker -> Gmail API
```

Recovery tokens remain encrypted at rest in the outbox. Provider exceptions expose only bounded error classifications and must not contain the recipient, verification URL, OAuth client secret, refresh token, or short-lived access token.

## Worker

The delivery worker entry point is unchanged:

```text
python -m processual_api.auth.delivery_worker --continuous --poll-interval-seconds 1
```

Do not start the worker with incomplete Gmail authority. Runtime configuration fails closed when the selected provider is missing required credentials or sender identity.
