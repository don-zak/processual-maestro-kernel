# ADMIN-MARKET-R1 — Domain and Authority Contracts

## Scope

This phase defines immutable Admin Marketplace domain, exclusive authority,
sales-channel choice, and commercial audit contracts. It intentionally adds no
persistence, migration, HTTP route, checkout, webhook, activation runtime, or UI.

## Accepted authority

- `platform_admin` is the only accepted marketplace authority.
- `platform_supervisor`, delegated or specialized administrators, customers,
  institutions, unauthenticated actors, and wildcard authorities are denied.
- Sensitive commercial actions require recent MFA step-up.
- Runtime adapters must continue to verify active platform authority and MFA
  through the existing authentication database-backed controls.

## Sales-channel policy

Tunisian customers and institutions may be eligible for both Maestro Direct and
Lemon Squeezy. Tunisia alone is not a denial condition. Ineligibility requires a
documented restriction reason, review states prohibit automatic activation, and
customer selection must remain within eligible channels.

## Exit assertions

```text
AdminMarketplaceContractsDefined=True
SuperAdministratorExclusiveAuthority=True
DelegatedSupervisorDenied=True
WildcardCommercialAuthorityDenied=True
SensitiveCommercialStepUpRequired=True
CommercialAuditContractImmutable=True
TunisiaCustomerChannelChoicePreserved=True
PersistenceAdded=False
RuntimeCheckoutEnabled=False
UIAdded=False
```
