# Group 2 — Commercial Catalog and Entitlement Contracts

## Purpose

This stage binds the selected Maestro prices to draft catalog, quota, and
entitlement contracts without publishing or activating any commercial flow.

## Plan mapping

| Plan | Audience | Visibility | Included units | Seat policy |
|---|---|---|---:|---|
| Academic | Academic | Public candidate | 5,000 | Single-user candidate |
| Starter | Individual | Public candidate | 10,000 | Single-user candidate |
| Enterprise Integration Starter | Enterprise | Enterprise sales | 50,000 | Not seat based |
| Business | Business | Public candidate | 100,000 | Organization policy remains separate |
| Enterprise Pilot | Enterprise | Enterprise sales | 500,000 | Not seat based |
| Enterprise Core | Enterprise | Enterprise sales | 1,500,000 | Not seat based |
| Enterprise Scale | Enterprise | Enterprise sales | 3,000,000 | Not seat based |
| Enterprise Strategic | Enterprise | Contract only | 5,000,000 | Not seat based |

## Entitlement principles

All plans include:

- Maestro execution rights;
- BYOK provider connection;
- support appropriate to the plan.

Enterprise plans additionally include governed commercial operation. Advanced
integration is explicit for the integration starter, scale, and strategic
contracts.

## UI/UX implications

The actual frontend must consume these contracts through the program's existing
design system. It must clearly distinguish:

- public plan candidates;
- enterprise-sales plans;
- contract-only plans;
- draft or unavailable commercial states;
- included Maestro units;
- overage pricing;
- BYOK responsibility;
- plans that are not based on seat counts.

No standalone UI is introduced in this repository.

## Safety status

```text
Catalog status: draft_review
Catalog publication approved: false
Offer purchase enabled: false
Entitlement grant enabled: false
Quota enforcement enabled: false
Subscription migration enabled: false
BYOK only: true
```
