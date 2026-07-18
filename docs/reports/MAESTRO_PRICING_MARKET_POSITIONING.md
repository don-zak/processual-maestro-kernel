# Maestro Pricing Market Positioning

## Phase

PRICING-MARKET-01 — document market pricing and Maestro plan positioning.

## Purpose

This document records the pricing and quota positioning decision that must happen
before PRICING-UNITS-03 enforces usage-unit quota for API keys.

The goal is not to hard-code commercial pricing in the backend. The goal is to
avoid enforcing an arbitrary unit allowance before the product position is clear.

## Non-negotiable billing policy

Maestro uses BYOK as a product boundary:

1. Maestro issues Maestro API keys for access to Maestro services.
2. Maestro does not give customers provider keys owned by Maestro.
3. External LLM/provider spend belongs to the customer provider account.
4. Maestro billing is for Maestro usage units, governance value, integration
   features, support, storage, analytics, and SLA.
5. Provider token cost is not included in Maestro usage-unit pricing.

## Market references reviewed

The following market signals were reviewed before quota enforcement:

- Langfuse uses billable units and shows a pricing calculator where the first
  100k units are included in the base range, with published overage bands such
  as 8 USD per 100k units after that threshold.
- Portkey Production publishes 100k recorded logs/month at 49 USD/month with
  9 USD overage per additional 100k requests/logs, while Enterprise is custom
  and starts at much higher recorded-log volume.
- Helicone publishes a free Hobby tier, Pro at 79 USD/month, Team at
  799 USD/month, and custom Enterprise packages.
- LangSmith prices traces separately from seats and distinguishes shorter
  retention base traces from longer retention extended traces.
- Braintrust prices scores and processed data, with a Pro tier that includes
  50k scores and enterprise reserved for RBAC, export, premium support, and
  hosted or on-prem deployment.
- Kong Konnect shows that gateway pricing includes control planes, request
  volume, AI Gateway model proxy costs, analytics, metering, and enterprise
  add-ons.

## Product conclusion

Maestro should not be priced as a raw API Gateway.

The correct product category is:

AI Gateway + governance engine + usage ledger + enterprise integration key
management + observability/analytics + BYOK boundary.

Therefore, a low request or unit count alone must not define Enterprise.
Enterprise is justified by:

- production integration controls,
- service identity and scoped API keys,
- audit logs,
- usage visibility,
- quota enforcement,
- RBAC/SSO later,
- SLA and support,
- governance/reporting features,
- private or dedicated deployment later.

## Recommended allowance ladder

The recommended commercial positioning is:

| Plan | Monthly Maestro units | Product meaning |
| --- | ---: | --- |
| developer | 2,000 | internal/dev testing, not production integration |
| starter | 10,000 | light self-service usage |
| business | 100,000 | production team usage without full enterprise contract |
| enterprise_integration_starter | 50,000 | initial enterprise integration / pilot with light support |
| enterprise_integration | 500,000 | real enterprise integration with support and visibility |
| enterprise_custom | configurable | annual/custom contract, SLA, SSO/RBAC, custom retention/deployment |

## Important correction to prior assumption

50,000 Maestro units/month should not be presented as the main Enterprise
Integration tier.

It is better positioned as:

enterprise_integration_starter = 50,000 units/month

The main enterprise integration tier should be larger, for example:

enterprise_integration = 500,000 units/month

This keeps Maestro aligned with market references where 50k to 100k events,
logs, traces, or scores often live in self-service, pro, or team pricing, while
Enterprise is justified by support, compliance, governance, and deployment
requirements.

## Enforcement guidance for PRICING-UNITS-03

PRICING-UNITS-03 may enforce usage-unit quota only after this positioning is
accepted.

The enforcement implementation should:

1. continue recording the pricing metadata added in PRICING-UNITS-02;
2. read the monthly unit allowance from plan identity;
3. keep BYOK metadata explicit in rejection/usage records;
4. reject only when a metered API-key request would exceed the active unit
   allowance;
5. keep free operational endpoints at 0 units;
6. avoid embedding USD prices in backend enforcement logic;
7. make enterprise_custom configurable rather than fixed;
8. preserve auditability with quota_before, quota_after, units_charged,
   plan_id, subscription_id, client_id, and api_key_id.

## Backend implementation note

The current backend can keep price amounts out of code. It should store and
enforce allowances, not dollars.

Commercial price packaging can live in documentation, billing configuration,
or admin-managed plan metadata later.
