# PRICING-TERMS-09C — Draft Commercial Terms Review

Status: `draft_review`.
Public terms approved: `false`.
Public pricing approved: `false`.
Checkout approved: `false`.
Lemon Squeezy wiring approved: `false`.
Currency approved: `false`.

This document is an internal commercial terms review checklist. It does not approve
public pricing, checkout, Lemon Squeezy variants, tax treatment, Merchant of Record
treatment, final refund wording, or legally binding terms.

The goal of 09C is to define what must be reviewed before Maestro can publish
commercial terms or prepare an approval-ready public price book.

## 1. Commercial terms guardrails

The following guardrails apply until a later approval phase:

- Pricing remains unapproved.
- Currency remains unapproved.
- Checkout remains disabled.
- Lemon Squeezy variant IDs remain forbidden.
- Public legal terms remain unapproved.
- Public refund terms remain unapproved.
- Tax and Merchant of Record treatment remain unapproved.
- Enterprise and telecom-grade integration remain review-led.
- Subscription pricing and integration pricing remain separate.
- BYOK remains required.
- AI provider costs remain excluded from Maestro pricing.

## 2. What the subscription may include

Standard subscription offers may include:

- access to the Maestro application;
- a monthly usage allowance;
- standard product features available to the selected plan;
- standard onboarding material;
- limited product support according to plan level;
- standard account and workspace configuration;
- standard usage and billing visibility;
- client-side BYOK provider configuration support.

Standard subscription offers do not automatically include custom implementation,
production API integration, telecom-grade connectors, data migration, custom SLA,
managed rollout, or dedicated operational supervision.

## 3. What must remain excluded unless separately scoped

The following items require separate review, pricing, and approval:

- production API integration;
- telecom-grade integration;
- custom adapters;
- custom workflow design;
- customer-specific API mapping;
- security review beyond standard application controls;
- private deployment;
- dedicated infrastructure;
- data migration;
- managed rollout;
- custom SLA;
- write access to production customer, billing, order, ticketing, or network systems;
- post-launch stabilization beyond the agreed support boundary.

## 4. BYOK and provider-cost wording

Maestro pricing must clearly state that BYOK is required unless a later approved
commercial model says otherwise.

AI provider costs are external to Maestro pricing. The customer is responsible for
provider accounts, usage charges, rate limits, provider availability, and provider
policy compliance.

Maestro may help the customer configure provider access, but that assistance does not
mean Maestro absorbs AI provider costs or guarantees third-party provider behavior.

## 5. Paid trial review checklist

Paid trial wording must clarify:

- the trial duration;
- whether usage is capped;
- whether the trial renews automatically;
- whether conversion to subscription is manual or automatic;
- what happens when the trial ends;
- whether unused usage rolls over;
- whether support is included;
- what refund terms apply;
- whether Enterprise evaluation is excluded from the paid trial.

Paid trial must not be treated as Enterprise approval. Enterprise evaluation remains
review-led and separately scoped.

## 6. Refund terms review checklist

Refund terms must be reviewed before publication. The final wording should clarify:

- refund eligibility window;
- refund request process;
- excluded costs;
- consumed usage treatment;
- abuse or excessive-use exceptions;
- provider-cost exclusion;
- tax and payment processor limitations;
- Enterprise and custom integration exclusion.

Refund language must not imply that Maestro refunds third-party AI provider charges.

## 7. Tax and Merchant of Record checklist

Before public checkout can be enabled, the team must decide:

- base currency;
- whether prices are tax-inclusive or tax-exclusive;
- tax collection responsibility;
- Merchant of Record model;
- payment processor;
- invoice wording;
- refund handling;
- customer country restrictions;
- required business identity fields.

Lemon Squeezy or any other Merchant of Record must not be wired until this checklist
is approved.

## 8. Support limits by offer class

Support limits must be reviewed by offer class:

| Offer class | Support posture | Review note |
| --- | --- | --- |
| Pilot Starter | Light product support | Avoid custom consulting. |
| Pilot Pro | Standard product support | Keep scope standardized. |
| Institution Trial | Guided evaluation support | Prevent unpaid implementation work. |
| Enterprise Private | Scoped operational support | Define response expectations manually. |
| Telecom-grade integration | Project support | Govern through project scope and acceptance criteria. |

Public terms should avoid open-ended support promises.

## 9. Data retention and workspace limits checklist

Commercial terms should define:

- workspace retention policy;
- usage log retention;
- audit event retention;
- client export expectations;
- account closure process;
- deletion request process;
- backup limitations;
- Enterprise retention exceptions;
- legal hold or compliance exceptions if applicable.

These items must be reviewed before public legal terms are published.

## 10. Fair-use and usage-limit checklist

Usage wording should define:

- monthly allowance;
- what counts as a unit;
- what happens when allowance is exceeded;
- whether overage exists;
- whether rollover exists;
- throttling or suspension behavior;
- abuse prevention;
- high-volume review threshold;
- Enterprise custom allowance treatment.

No public overage or rollover promise should be made before approval.

## 11. Enterprise review policy

Enterprise review is required when a customer requests:

- private deployment;
- custom governance;
- privileged integrations;
- production API access;
- custom SLA;
- dedicated support;
- sensitive data workflows;
- security review;
- contractual terms outside standard offers.

Enterprise review must include scoping, commercial review, technical review, and
supervisor or operations involvement before approval.

## 12. Telecom-grade integration policy

Telecom-grade integration is a separate project class. It may involve CRM, billing,
order management, ticketing, OSS/BSS, network assurance, API gateway integration,
staging environments, production cutover, acceptance testing, and post-launch
stabilization.

Telecom-grade integration is not included in standard subscription pricing. It must
require separate scoping, technical contacts, API documentation, sandbox access,
credentials policy, security review, and acceptance criteria.

## 13. Publication restrictions

This document must not be used as:

- public legal terms;
- public pricing approval;
- checkout approval;
- Lemon Squeezy configuration;
- tax approval;
- Merchant of Record approval;
- refund policy approval;
- Enterprise SLA approval;
- telecom integration approval.

Public commercial terms can only be published after a later approval phase confirms
pricing, currency, tax handling, Merchant of Record treatment, refund wording,
support boundaries, retention boundaries, usage boundaries, Enterprise review rules,
and checkout behavior.
