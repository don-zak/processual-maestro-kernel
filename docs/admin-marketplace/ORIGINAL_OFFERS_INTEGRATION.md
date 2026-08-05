# Admin Market — Original Offers Integration Contract

## Scope

Connect the existing application offer pricebook to the Admin Market Catalog / Offers workspace without creating a second competing offer catalog.

Canonical source:

- `processual_api.billing.offer_pricebook.public_offer_pricebook`
- existing public route: `GET /billing/offer-pricebook`

The source pricebook is currently a draft-review catalog. Its offers must not become purchasable merely because they are visible in Admin Market.

## Mandatory commercial gates

A local payment option is eligible only when all server-side gates pass:

1. Customer eligibility is trusted and current.
2. `country_code == "TN"`.
3. `address_status == "confirmed"`.
4. The selected commercial offer is published for `maestro_direct`.
5. The offer currency is `TND`.
6. The offer is inside its effective window.
7. An active and default Tunisian payment destination exists.

Any missing, unknown, stale, or contradictory value fails closed. A typed address in the browser is never sufficient evidence.

## Catalog / Offers workspace

Admin Market must display the original offer identity and safe commercial metadata:

- offer ID
- plan ID and display name
- offer display name and description
- billing interval
- commercially listed flag
- sales-contact requirement
- pricebook version and status
- price status
- checkout-enabled flag
- fulfillment mode

The panel must clearly distinguish:

- source offer visibility
- local-channel qualification
- publication/readiness for customer checkout

Showing an offer does not publish it, price it, or enable checkout.

## Payment destination input

The existing Admin Market Payment Destinations workspace remains the only administration surface for Tunisian receiving destinations.

Required fields remain:

- destination reference
- display name
- destination type
- institution
- account holder
- raw account identifier (password input; one-time submission)
- non-sensitive customer instructions

Fixed values remain visible and server-controlled:

- country: `TN`
- currency: `TND`
- channel: `maestro_direct`

The primary submit action is `Validate destination` and calls the existing atomic create-and-validate operation. Successful validation must:

- store the sensitive identifier encrypted
- return only a masked identifier
- clear the raw identifier from the browser
- render the validated result in Admin Market

Validation must not activate the destination or set it as default. `Activate` and `Set default` remain separate MFA-gated lifecycle actions.

## Results shown in Admin Market

The Admin Market must display:

- original offers and their source status
- payment destinations with masked identifiers only
- destination lifecycle state
- active/default readiness
- orders, contracts, payment evidence, reconciliation, and activations already exposed by the direct-flow APIs

No raw account identifiers, transfer references, ciphertext, Outbox payload, or unsafe audit metadata may be rendered.

## API direction

Add an authenticated, platform-admin read endpoint:

`GET /admin-marketplace/catalog/offers`

The endpoint should adapt `public_offer_pricebook()` into an Admin Market safe DTO and may add computed readiness fields. It must not trust browser-provided eligibility or publication state.

Suggested response shape:

```json
{
  "source": "billing.offer_pricebook",
  "pricebook_version": "...",
  "pricebook_status": "...",
  "checkout_enabled": false,
  "items": []
}
```

## Tests

Minimum coverage:

1. Admin authority is required for the catalog endpoint.
2. Returned offers match the canonical offer pricebook IDs.
3. Draft source offers remain non-purchasable.
4. No local payment option for a non-Tunisian customer.
5. No local payment option for an unconfirmed Tunisian address.
6. Confirmed `TN` eligibility still requires a published TND `maestro_direct` offer.
7. Confirmed `TN` eligibility still requires an active default destination.
8. Create-and-validate clears raw identifier and returns masked data only.
9. Validate does not activate or set default.
10. Admin Market renders loading, empty, forbidden, failure, and ready states.

## Acceptance rule

The integration is accepted only when the original offers appear in Admin Market while the customer-side local payment route remains fail-closed unless every trusted Tunisia, offer, and destination gate passes.
