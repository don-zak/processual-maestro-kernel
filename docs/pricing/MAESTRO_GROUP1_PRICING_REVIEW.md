# Maestro Group 1 — Integrated Pricing Review

## Consolidated scope

```text
Measurement evidence
→ Maestro usage unit
→ internal cost factor
→ commercial value factor
→ quota simulation
→ price determination for review
```

No additional roadmap phases are created inside this group.

## Status

```text
Pricing status: draft_review
Currency: USD
BYOK only: true
AI-provider cost included: false
Commercial enforcement: disabled
Approved for quota: false
Approved for pricing: false
Approved for invoicing: false
Approved for checkout: false
Approved for settlement: false
```

## Maestro usage unit

| Quantity | Weight |
|---|---:|
| Base execution | 1.00 |
| Integration action | 0.25 |
| Equivalent page | 0.04 |
| Record processed | 0.001 |
| Verification item | 0.04 |
| Standard supervision gate | 2.00 |
| Extended supervision gate | 5.00 |
| Excess storage GB-month | 1.00 |

Resource multipliers:

```text
normal = 1.00
heavy = 1.25
extreme = 1.50
custom = manual review
```

## Cost factor

The internal cost factor includes provisional allocations for:

- infrastructure;
- operations;
- support;
- fixed costs;
- retries and failed attempts;
- risk reserve;
- payment processing;
- tax reserve;
- target net margin.

AI-provider cost remains excluded under BYOK.

## Commercial value factor

The customer-facing unit remains stable. Commercial value is applied behind
the unit as a plan-level multiplier:

```text
standard = 1.00
advanced = 1.08
academic research = 1.12
enterprise governed = 1.18
custom = manual review
```

This prevents exposing several confusing unit types while allowing pricing to
reflect research depth, governance, support, and institutional value.

## Review scenarios

```text
conservative: 30% target margin, no uniqueness premium
recommended: 40% target margin, 10% uniqueness premium
resilient: 50% target margin, 10% uniqueness premium
```

These are engineering review assumptions, not approved accounting or market
facts.

## Stop gate

Execution stops at the generated price table. No price may be published or
connected to checkout before explicit review and approval.

## Adopted enterprise reference ladder

The enterprise offer is not defined by a fixed number of seats. It is defined
by monthly Maestro units, operational scope, governance, integrations, support,
and contractual service requirements.

| Reference tier | Monthly Maestro units | Intended scope |
|---|---:|---|
| Enterprise Pilot / Starter | 500,000 | Wide pilot, one major department, or a bounded institutional scope |
| Enterprise Core | 1,500,000 | Moderate production use across several departments |
| Enterprise Scale | 3,000,000 | Broad institutional adoption and multiple integrated workflows |
| Enterprise Strategic | 5,000,000+ | Intensive strategic use, large integrations, and high automation volume |
| Enterprise Custom | Measured contract | Flexible quota, SLA, governance, and commercial review |

### Governing interpretation

- 500,000 units are an enterprise entry or pilot tier, not an automatic full-enterprise allowance.
- Large institutions are sized by workflows, frequency, volume, resource band,
  verification, supervision, integrations, support, security, and governance.
- Enterprise quotas are not tied to a fixed seat count.
- Enterprise Custom remains a negotiated and measured contract.
- The recommended pricing scenario remains the default commercial basis.
- Prices remain `draft_review`.
- Checkout, invoicing, settlement, and quota enforcement remain disabled.

