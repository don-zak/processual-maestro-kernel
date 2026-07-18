# PRICING-REVIEW-09A — Draft Market Pricing Review

Status: `draft_review`
Public pricing approved: `false`
Checkout approved: `false`
Lemon Squeezy wiring approved: `false`
Currency approved: `false`
Provider cost policy: `BYOK; AI provider costs excluded`

## Purpose

This document prepares a draft commercial pricing list for Processual Maestro after reviewing comparable AI gateway, LLM observability, and agent operations platforms.

This document is internal review material only. It must not be rendered as approved public pricing until commercial, accounting, tax, and legal review are complete.

## Comparable market references

Reviewed public pricing patterns:

- LangSmith: free developer entry, paid team plan around seat-based pricing, enterprise custom.
- Langfuse: low-cost Core, mid-market Pro, higher enterprise plan, plus usage-based units.
- Portkey: developer/free entry, production plan, overage model, enterprise custom.
- Helicone: free/hobby entry, Pro, Team, Enterprise custom.

Market conclusion:

- Simple observability and gateway tooling can start at low monthly prices.
- Enterprise, private deployment, compliance, SSO, support SLA, and dedicated onboarding are generally custom or substantially higher.
- Processual Maestro should not be priced as a pure logging tool. It combines orchestration, supervision, billing readiness, client request workflow, BYOK policy, admin governance, and integration support.
- Self-service plans should remain accessible.
- Enterprise integration must remain custom and separate from normal self-service plans.

## Draft pricing principles

1. Do not publish cost calculation formulas.
2. Do not publish profit margin assumptions.
3. Do not include AI provider costs; BYOK applies.
4. Keep infrastructure, payment processing, tax handling, supervision, support, and operational risk as internal cost factors.
5. Separate subscription revenue from one-time enterprise integration fees.
6. Keep checkout disabled until final prices, currency, taxes, and terms are approved.
7. Keep enterprise review separate from public paid trials.
8. Prefer annual discounts only after monthly price validation.

## Draft price list for consultation

| Plan | Draft monthly range | Included units | Intended use | Fulfillment |
|---|---:|---:|---|---|
| Pilot Starter | 49–79 USD | 50 | Individual or small proof of concept | Self-service after payment when checkout is approved |
| Pilot Pro | 149–249 USD | 500 | Small team or regular internal usage | Self-service after payment when checkout is approved |
| Institution Trial | 499–899 USD | 2,000 | Institutional review, training center, university, department | Self-service or light review depending account type |
| Enterprise Private | from 2,500–7,500 USD | Custom | Telecom, bank, large institution, private deployment | Supervisor review and custom contract |

## Draft setup and integration fees

| Item | Draft one-time range | Notes |
|---|---:|---|
| Standard onboarding | 500–1,500 USD | Light onboarding, workspace preparation, first usage review |
| Advanced workflow setup | 2,500–7,500 USD | Multiple workflows, admin setup, usage policies, reporting |
| Enterprise API integration | 10,000–50,000 USD | API integration, SSO, security review, private routing, audit needs |
| Telecom-grade integration | 25,000–100,000 USD | Higher range only if private deployment, SLA, security, multi-team rollout, or regulated review is required |

## Recommended starting point

For public launch review:

- Pilot Starter: 59 USD / month candidate
- Pilot Pro: 199 USD / month candidate
- Institution Trial: 699 USD / month candidate
- Enterprise Private: custom, starting from 3,500 USD / month
- Enterprise API integration: custom, starting from 15,000 USD one-time

These are review candidates, not approved prices.

## Items requiring consultation before approval

- Final billing currency.
- Tunisia tax/accounting handling.
- Merchant-of-record behavior.
- Refund terms final legal wording.
- Annual discount policy.
- Overage policy.
- Whether units should reset monthly only or support rollover.
- Whether paid trial converts automatically or requires confirmation.
- Whether institution trial requires manual review.
- Enterprise SLA bands.
- Support response time.
- Data retention and audit export commitments.
- Private deployment pricing.

## Public communication guidance

Allowed public wording:

> Pricing is under review. Processual Maestro considers infrastructure, payment processing, applicable tax handling, support, supervision, and operational risk when setting prices. BYOK applies, and AI provider costs are not included.

Not allowed in public wording:

- Internal cost calculation details.
- Profit margin targets.
- Risk buffer amounts.
- Tax reserve amounts.
- Server or database cost values.
- Lemon/payment fee formula.
- Approved prices before final review.

## Decision

Keep the current public pricing surface as draft/pending review. Do not wire checkout. Do not publish final prices until the commercial review is complete.

---

## PRICING-REVIEW-09B Consultation Offer Strategy

Status: `draft_review`.

This section refines the internal consultation offer strategy. It does not approve
public prices, currency, checkout, Lemon Squeezy wiring, tax treatment, or final
commercial terms.

These figures and ratios are internal review candidates only. They must not be
rendered on `/pricing`, must not be wired to checkout, and must not be used as
Lemon Squeezy variants or public price-book amounts.

### 09B.1 Offer strategy guardrails

The consultation strategy is based on the following guardrails:

- BYOK remains required.
- AI provider costs remain excluded from Maestro pricing.
- Public pricing remains unapproved.
- Currency remains unapproved.
- Checkout remains disabled.
- Lemon Squeezy variant IDs remain forbidden until approval.
- Enterprise and telecom-grade integration remain review-led and scoped manually.
- Subscription revenue and integration revenue must be reviewed separately.

### 09B.2 Candidate price posture

The ranges below are still review candidates, not approved public prices.

| Offer | Low candidate | Recommended candidate | High candidate | Review posture |
| --- | ---: | ---: | ---: | --- |
| Pilot Starter | 49 USD / month | 59 USD / month | 79 USD / month | Keep support light and self-service-oriented. |
| Pilot Pro | 149 USD / month | 199 USD / month | 249 USD / month | Preferred early SaaS plan when usage is repeatable. |
| Institution Trial | 499 USD / month | 699 USD / month | 899 USD / month | Use for structured institutional evaluation. |
| Enterprise Private | 2,500 USD / month | 5,000 USD / month | 7,500 USD / month | Use only after scoping and operational review. |

The recommended candidate is not an approved price. It is a review anchor for
comparing cost, support effort, operational load, and expected margin.

### 09B.3 Expense-to-revenue guardrails

Expense-to-revenue ratios are internal planning guardrails. They exclude AI provider
costs because the current policy is BYOK.

| Offer | Acceptable expense ratio | Target expense ratio | Target gross margin before taxes |
| --- | ---: | ---: | ---: |
| Pilot Starter | 25% to 45% | About 30% | About 70% |
| Pilot Pro | 20% to 40% | 25% to 30% | 70% to 75% |
| Institution Trial | 25% to 45% | 30% to 35% | 65% to 70% |
| Enterprise Private | 30% to 55% | 35% to 45% | 55% to 65% |
| Telecom-grade integration | 35% to 60% | 40% to 55% | 45% to 60% |

If a plan repeatedly exceeds its acceptable expense ratio, it should be reviewed for
repricing, reduced support scope, conversion to Enterprise, or conversion to a
separately scoped integration project.

### 09B.4 Plan rationale

#### Pilot Starter

Pilot Starter exists to let a small customer validate the product with limited usage,
limited support, and no custom integration. It should not include production API
integration, custom workflow setup, custom SLA, or dedicated operational supervision.

#### Pilot Pro

Pilot Pro is the preferred entry plan for a serious small team. It may include more
usage and stronger onboarding guidance, but it should remain standardized and should
not absorb custom implementation work.

#### Institution Trial

Institution Trial is for a structured institutional evaluation. It may involve more
users, more review meetings, and more usage, but it remains a trial and should not
become unpaid consulting or production-grade integration.

#### Enterprise Private

Enterprise Private is for customers requiring privacy, operational review, stronger
supervision, special deployment expectations, or custom governance. It should be
scoped manually and should not be sold as self-service.

#### Telecom-grade integration

Telecom-grade integration is not a normal subscription feature. It is a separately
scoped project that may involve CRM, billing, ticketing, order management, OSS/BSS,
network assurance, API gateways, staging environments, security review, and production
acceptance testing.

### 09B.5 Plan escalation rules

Use the following escalation rules during commercial review:

- Starter should escalate to Pro when repeated usage, support needs, or team usage
  exceed light pilot expectations.
- Pro should escalate to Institution Trial when the buyer is evaluating across a
  department, institution, or multi-user workflow.
- Institution Trial should escalate to Enterprise Private when the customer requests
  private deployment, custom governance, SLA commitments, privileged access, or
  production integration.
- Enterprise Private should escalate to telecom-grade integration when the customer
  requires integration with telecom CRM, billing, ticketing, order management,
  network assurance, OSS/BSS, or API gateway infrastructure.
- Any write action against a production customer, billing, order, or network system
  requires scoped review and should not be bundled into standard subscription pricing.

### 09B.6 Integration pricing separation

Subscription pricing and integration pricing must remain separate.

Standard subscriptions may cover access, usage allowance, product support, and
standardized onboarding. They do not automatically include production integration,
telecom-grade connectors, customer-specific API mapping, data migration, or managed
rollout.

Enterprise API integration and telecom-grade integration require scoping before price
approval. The customer should provide API documentation, sandbox access, security
requirements, rate limits, expected workflows, technical contacts, and acceptance
criteria before the project is priced.

Integration pricing should account for:

- discovery and process mapping;
- API contract review;
- staging and production environment separation;
- authentication and credential handling;
- security and compliance review;
- adapter development and validation;
- audit and supervisor approval flows;
- acceptance testing;
- rollout support;
- post-launch stabilization.

### 09B.7 Publication restrictions

The 09B consultation strategy must not be used as:

- approved public pricing;
- `/pricing` page content;
- checkout configuration;
- Lemon Squeezy variant configuration;
- tax or Merchant of Record approval;
- a promise of included telecom integration;
- a public SLA;
- a public refund policy.

Public pricing can only be introduced after a later approval phase confirms price,
currency, taxes, refund terms, Merchant of Record treatment, checkout behavior,
support limits, and Enterprise review rules.
