# Lemon Squeezy Real Provider Qualification

## Purpose

This stage converts the existing Lemon Squeezy repository contracts into a controlled real-provider test-mode qualification. It is intentionally independent of GCP and must not grant staging or production authority by itself.

## Existing authority chain

The repository already contains a signed webhook route, durable inbox/reconciliation, provider/customer ownership bindings, subscription lifecycle reconciliation, subscription activation, and authoritative quota bootstrap. The real-provider exercise must reuse those paths rather than create a parallel subscription authority.

## Preflight

Set the following only in the local/runtime environment; do not commit their values:

- `LEMONSQUEEZY_API_KEY`
- `LEMONSQUEEZY_WEBHOOK_SECRET`
- `LEMONSQUEEZY_STORE_ID`

Then run:

```powershell
.\scripts\Test-PMKLemonSqueezyProviderPreflight.ps1
```

The script writes `.pmk-validation/lemon-squeezy-provider-preflight.json`. It records presence/validity only and never stores secret values.

## Real provider proof required

A complete test-mode qualification must retain independently reviewable evidence for:

1. authenticated API access to the intended test-mode store;
2. a verified internal offer -> Lemon Squeezy variant binding;
3. checkout creation carrying the authoritative internal order reference;
4. HTTPS webhook delivery to `/billing/webhook` with a valid signature;
5. store, customer, variant, amount, currency and order-reference reconciliation;
6. exact replay/idempotency behavior for the same provider event;
7. subscription activation through the existing authoritative activation service;
8. authoritative quota bootstrap in the same subscription authority chain;
9. cancellation/refund lifecycle behavior;
10. fail-closed handling of bad signature, wrong store, wrong variant, amount/currency mismatch and provider/API uncertainty.

## Authority boundary

Until all real-provider evidence above exists:

- `RealProviderQualified=false`
- `RealStagingQualified=false`
- `ProductionAuthorityGranted=false`
- `Commercial Launch=NO_GO`

This stage is useful specifically because it adds real external-provider evidence while GCP remains unavailable; it does not substitute for real cloud staging.
